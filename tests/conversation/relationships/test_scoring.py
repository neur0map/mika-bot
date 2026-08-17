"""Deterministic, scoped scoring for relationship-memory candidates."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from mika.conversation.context.contracts import MemoryCandidate, RetrievalScope
from mika.conversation.relationships.scoring import (
    AttributedRecallFeedback,
    HybridMemoryScorer,
    ScoringWeights,
)

_NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)
_SCOPE = RetrievalScope("u1", "guild", "g1", "c1")


def _candidate(
    candidate_id: str,
    text: str,
    *,
    subject_user_id: str = "u1",
    visibility_kind: str = "channel",
    guild_id: str | None = "g1",
    channel_id: str | None = "c1",
    evidence_class: str = "repeated_behavior",
    confidence: float = 0.7,
    age_days: int = 1,
) -> MemoryCandidate:
    return MemoryCandidate(
        candidate_id=candidate_id,
        subject_user_id=subject_user_id,
        visibility_kind=visibility_kind,
        guild_id=guild_id,
        channel_id=channel_id,
        kind="claim",
        index_text=text,
        overview_text=f"Overview: {text}",
        evidence_text=f"Evidence: {text}",
        evidence_class=evidence_class,
        confidence=confidence,
        observed_at=_NOW - timedelta(days=age_days),
    )


def test_scope_rejects_other_people_and_invisible_channels_before_scoring() -> None:
    candidates = (
        _candidate("visible", "launch checklist"),
        _candidate("other-person", "launch checklist", subject_user_id="u2"),
        _candidate("other-channel", "launch checklist", channel_id="c2"),
        _candidate(
            "private",
            "launch checklist",
            visibility_kind="direct_message",
            guild_id=None,
            channel_id="dm1",
        ),
        _candidate("legacy", "launch checklist", visibility_kind="legacy_unscoped"),
        _candidate(
            "global-correction",
            "launch checklist",
            visibility_kind="global_explicit",
            guild_id=None,
            channel_id=None,
            evidence_class="correction",
        ),
    )

    result = HybridMemoryScorer().rank("launch", candidates, _SCOPE, now=_NOW)

    assert [item.candidate_id for item in result.ranked] == ["visible"]
    assert result.rejection_reasons == {
        "other-person": "subject_mismatch",
        "other-channel": "channel_scope_mismatch",
        "private": "direct_message_scope_mismatch",
        "legacy": "unresolved_legacy_scope",
        "global-correction": "invalid_global_scope",
    }


def test_correction_priority_outranks_confidence_recency_and_lexical_overlap() -> None:
    correction = _candidate(
        "correction",
        "deployment preference clarified",
        evidence_class="correction",
        confidence=0.6,
        age_days=90,
    )
    inferred = _candidate(
        "inference",
        "deployment preference observed repeatedly",
        evidence_class="inference",
        confidence=1.0,
        age_days=0,
    )

    result = HybridMemoryScorer().rank(
        "deployment preference", (inferred, correction), _SCOPE, now=_NOW
    )

    assert [item.candidate_id for item in result.ranked] == ["correction", "inference"]
    assert result.ranked[0].score_components["correction"] > 0
    assert (
        result.ranked[0].score_components["evidence"]
        > result.ranked[1].score_components["evidence"]
    )


def test_confidence_recency_and_lexical_overlap_are_inspectable_components() -> None:
    candidates = (
        _candidate("weak", "launch planning", confidence=0.4, age_days=80),
        _candidate("strong", "launch planning checklist", confidence=0.9, age_days=1),
    )

    result = HybridMemoryScorer().rank("launch checklist", candidates, _SCOPE, now=_NOW)

    assert [item.candidate_id for item in result.ranked] == ["strong", "weak"]
    details = result.ranked[0].score_components
    assert set(details) == {
        "correction",
        "evidence",
        "confidence",
        "recency",
        "lexical",
        "semantic",
        "feedback",
    }
    assert details["confidence"] > result.ranked[1].score_components["confidence"]
    assert details["recency"] > result.ranked[1].score_components["recency"]
    assert details["lexical"] > result.ranked[1].score_components["lexical"]


def test_semantic_contribution_is_capped_and_cannot_beat_correction_priority() -> None:
    class Semantic:
        def score(self, query: str, documents: tuple[str, ...]) -> tuple[float, ...]:
            return (0.0, 99.0)

    weights = ScoringWeights(semantic=5.0, semantic_cap=0.2)
    correction = _candidate("correction", "editor choice", evidence_class="correction")
    inference = _candidate("semantic", "keyboard layout", evidence_class="inference")

    result = HybridMemoryScorer(weights).rank(
        "editor choice",
        (correction, inference),
        _SCOPE,
        now=_NOW,
        semantic_scorer=Semantic(),
    )

    assert result.ranked[0].candidate_id == "correction"
    semantic = next(item for item in result.ranked if item.candidate_id == "semantic")
    assert semantic.score_components["semantic"] == 0.2


def test_near_duplicate_candidates_do_not_consume_the_ranked_result() -> None:
    candidates = (
        _candidate("first", "prefers concise deployment checklists"),
        _candidate("duplicate", "prefers concise deployment checklist"),
        _candidate("different", "enjoys cooperative puzzle games"),
    )

    result = HybridMemoryScorer(minimum_score=0.0).rank(
        "deployment puzzle", candidates, _SCOPE, now=_NOW
    )

    assert [item.candidate_id for item in result.ranked] == ["first", "different"]
    assert result.rejection_reasons["duplicate"] == "near_duplicate:first"


def test_semantic_failure_has_deterministic_lexical_fallback() -> None:
    class BrokenSemantic:
        def score(self, query: str, documents: tuple[str, ...]) -> tuple[float, ...]:
            raise RuntimeError("offline")

    candidates = (
        _candidate("alpha", "launch checklist"),
        _candidate("beta", "garden notes"),
    )
    scorer = HybridMemoryScorer(minimum_score=0.0)

    fallback = scorer.rank("launch", candidates, _SCOPE, now=_NOW, semantic_scorer=BrokenSemantic())
    lexical = scorer.rank("launch", candidates, _SCOPE, now=_NOW)

    assert [(item.candidate_id, item.score) for item in fallback.ranked] == [
        (item.candidate_id, item.score) for item in lexical.ranked
    ]
    assert all(item.score_components["semantic"] == 0 for item in fallback.ranked)


def test_feedback_signal_requires_three_distinct_attributed_outcomes() -> None:
    candidate = _candidate("claim", "launch checklist")
    two = (
        AttributedRecallFeedback("f1", ("claim",), "positive"),
        AttributedRecallFeedback("f2", ("claim",), "positive"),
    )
    three = (*two, AttributedRecallFeedback("f3", ("claim",), "negative"))
    scorer = HybridMemoryScorer()

    cold = scorer.rank("launch", (candidate,), _SCOPE, now=_NOW, feedback=two)
    ready = scorer.rank("launch", (candidate,), _SCOPE, now=_NOW, feedback=three)

    assert cold.ranking_quality_signal == 0
    assert cold.ranked[0].score_components["feedback"] == 0
    assert 0 < ready.ranking_quality_signal <= scorer.weights.feedback_cap
    assert ready.ranked[0].score_components["feedback"] == ready.ranking_quality_signal


def test_feedback_never_overrides_evidence_priority() -> None:
    correction = _candidate(
        "correction", "launch preference explicitly corrected", evidence_class="correction"
    )
    inference = replace(
        _candidate(
            "inference", "launch preference inferred from behavior", evidence_class="inference"
        ),
        confidence=correction.confidence,
        observed_at=correction.observed_at,
    )
    feedback = tuple(
        AttributedRecallFeedback(f"f{index}", ("inference",), "positive") for index in range(3)
    )

    result = HybridMemoryScorer().rank(
        "launch preference", (inference, correction), _SCOPE, now=_NOW, feedback=feedback
    )

    assert [item.candidate_id for item in result.ranked] == ["correction", "inference"]


def test_correction_precedence_is_structural_even_when_explicit_score_is_higher() -> None:
    correction = _candidate(
        "correction",
        "clarified editor choice",
        evidence_class="correction",
        confidence=0.0,
        age_days=3_650,
    )
    explicit = _candidate(
        "explicit",
        "launch preference",
        evidence_class="explicit",
        confidence=1.0,
        age_days=0,
    )

    result = HybridMemoryScorer().rank(
        "launch preference", (explicit, correction), _SCOPE, now=_NOW
    )

    assert [item.candidate_id for item in result.ranked] == ["correction", "explicit"]
