"""Inspectable local hybrid scoring for scoped relationship memories."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from mika.conversation.context.contracts import MemoryCandidate, RetrievalScope

_TOKEN_PATTERN = re.compile(r"[a-z0-9']{3,}", re.IGNORECASE)
_STOP_TOKENS = frozenset(
    {"and", "are", "for", "from", "has", "remember", "that"}
    | {"the", "this", "was", "what", "with", "you", "your"}
)
_EVIDENCE_STRENGTH = {
    "correction": 1.2,
    "explicit": 1.0,
    "repeated_behavior": 0.45,
    "reaction": 0.3,
    "inference": 0.1,
}
_POSITIVE_OUTCOMES = frozenset({"accepted", "helpful", "positive", "success"})
_NEGATIVE_OUTCOMES = frozenset({"negative", "rejected", "unhelpful"})
_MINIMUM_ATTRIBUTED_FEEDBACK = 3
_PLURAL_STEM_LENGTH = 4


class SemanticScorer(Protocol):
    """Optional bounded semantic similarity provider."""

    def score(self, query: str, documents: tuple[str, ...]) -> Sequence[float]: ...


@dataclass(frozen=True, slots=True)
class AttributedRecallFeedback:
    """One content-free ranking outcome attributed to selected candidates."""

    feedback_id: str
    selected_candidate_ids: tuple[str, ...]
    outcome: str


@dataclass(frozen=True, slots=True)
class ScoringWeights:
    """Weights for every inspectable hybrid-ranking component."""

    correction: float = 1.4
    evidence: float = 1.0
    confidence: float = 0.6
    recency: float = 0.4
    lexical: float = 1.2
    semantic: float = 0.35
    semantic_cap: float = 0.2
    feedback: float = 0.1
    feedback_cap: float = 0.1


@dataclass(frozen=True, slots=True)
class RankingResult:
    """Ranked candidates plus reasons for every candidate removed."""

    ranked: tuple[MemoryCandidate, ...]
    rejection_reasons: Mapping[str, str]
    ranking_quality_signal: float


class HybridMemoryScorer:
    """Scope, score, threshold, and diversify local memory candidates."""

    def __init__(
        self,
        weights: ScoringWeights | None = None,
        *,
        minimum_score: float = 0.8,
        duplicate_threshold: float = 0.8,
    ) -> None:
        self.weights = weights or ScoringWeights()
        self._minimum_score = max(0.0, minimum_score)
        self._duplicate_threshold = min(1.0, max(0.0, duplicate_threshold))

    def rank(
        self,
        query: str,
        candidates: Sequence[MemoryCandidate],
        scope: RetrievalScope,
        *,
        now: datetime,
        semantic_scorer: SemanticScorer | None = None,
        feedback: Sequence[AttributedRecallFeedback] = (),
    ) -> RankingResult:
        """Return deterministic candidates after scope and relevance gates."""
        eligible, rejected = _apply_scope(candidates, scope)
        semantics = _semantic_scores(query, eligible, semantic_scorer, self.weights)
        feedback_signals = _feedback_signals(eligible, feedback, self.weights)
        scored = [
            self._score_candidate(query, item, now, semantics[index], feedback_signals)
            for index, item in enumerate(eligible)
        ]
        scored.sort(key=lambda item: (_evidence_precedence(item), item.score), reverse=True)
        relevant: list[MemoryCandidate] = []
        for item in scored:
            has_relevance = item.score_components["lexical"] + item.score_components["semantic"] > 0
            is_anchor = item.evidence_class in {"correction", "explicit"}
            if item.score < self._minimum_score or (not has_relevance and not is_anchor):
                rejected[item.candidate_id] = "below_minimum_score"
                continue
            duplicate_of = _duplicate_of(item, relevant, self._duplicate_threshold)
            if duplicate_of is not None:
                rejected[item.candidate_id] = f"near_duplicate:{duplicate_of}"
                continue
            relevant.append(item)
        quality = _ranking_quality(feedback_signals, self.weights.feedback_cap)
        return RankingResult(tuple(relevant), rejected, quality)

    def _score_candidate(
        self,
        query: str,
        candidate: MemoryCandidate,
        now: datetime,
        semantic: float,
        feedback_signals: Mapping[str, float],
    ) -> MemoryCandidate:
        evidence_strength = _EVIDENCE_STRENGTH.get(candidate.evidence_class or "", 0.0)
        age_days = max(0.0, (now - candidate.observed_at).total_seconds() / 86_400)
        components = {
            "correction": (
                self.weights.correction if candidate.evidence_class == "correction" else 0.0
            ),
            "evidence": self.weights.evidence * evidence_strength,
            "confidence": self.weights.confidence * _unit(candidate.confidence),
            "recency": self.weights.recency / (1.0 + age_days / 30.0),
            "lexical": self.weights.lexical * _lexical_overlap(query, candidate.index_text),
            "semantic": semantic,
            "feedback": feedback_signals.get(candidate.candidate_id, 0.0),
        }
        return replace(candidate, score=sum(components.values()), score_components=components)


def _apply_scope(
    candidates: Sequence[MemoryCandidate], scope: RetrievalScope
) -> tuple[list[MemoryCandidate], dict[str, str]]:
    eligible: list[MemoryCandidate] = []
    rejected: dict[str, str] = {}
    for candidate in candidates:
        reason = _scope_rejection(candidate, scope)
        if reason is None:
            eligible.append(candidate)
        else:
            rejected[candidate.candidate_id] = reason
    return eligible, rejected


def _scope_rejection(candidate: MemoryCandidate, scope: RetrievalScope) -> str | None:
    if candidate.subject_user_id != scope.subject_user_id:
        return "subject_mismatch"
    validator = {
        "direct_message": _direct_message_scope_rejection,
        "channel": _channel_scope_rejection,
        "guild": _guild_scope_rejection,
        "global_explicit": _global_scope_rejection,
    }.get(candidate.visibility_kind)
    return "unresolved_legacy_scope" if validator is None else validator(candidate, scope)


def _direct_message_scope_rejection(
    candidate: MemoryCandidate, scope: RetrievalScope
) -> str | None:
    visible = scope.visibility_kind == "direct_message" and candidate.channel_id == scope.channel_id
    return None if visible else "direct_message_scope_mismatch"


def _channel_scope_rejection(candidate: MemoryCandidate, scope: RetrievalScope) -> str | None:
    visible = (
        scope.visibility_kind != "direct_message"
        and candidate.guild_id == scope.guild_id
        and candidate.channel_id == scope.channel_id
    )
    return None if visible else "channel_scope_mismatch"


def _guild_scope_rejection(candidate: MemoryCandidate, scope: RetrievalScope) -> str | None:
    visible = scope.visibility_kind != "direct_message" and candidate.guild_id == scope.guild_id
    return None if visible else "guild_scope_mismatch"


def _global_scope_rejection(candidate: MemoryCandidate, scope: RetrievalScope) -> str | None:
    del scope
    return None if candidate.evidence_class == "explicit" else "invalid_global_scope"


def _semantic_scores(
    query: str,
    candidates: Sequence[MemoryCandidate],
    scorer: SemanticScorer | None,
    weights: ScoringWeights,
) -> tuple[float, ...]:
    if scorer is None or not candidates:
        return (0.0,) * len(candidates)
    try:
        values = tuple(scorer.score(query, tuple(item.index_text for item in candidates)))
    except Exception:
        return (0.0,) * len(candidates)
    if len(values) != len(candidates):
        return (0.0,) * len(candidates)
    cap = max(0.0, weights.semantic_cap)
    return tuple(min(cap, max(0.0, weights.semantic * _unit(value))) for value in values)


def _feedback_signals(
    candidates: Sequence[MemoryCandidate],
    feedback: Sequence[AttributedRecallFeedback],
    weights: ScoringWeights,
) -> dict[str, float]:
    signals: dict[str, float] = {}
    for candidate in candidates:
        attributed = {
            item.feedback_id: item
            for item in feedback
            if candidate.candidate_id in item.selected_candidate_ids
        }
        if len(attributed) < _MINIMUM_ATTRIBUTED_FEEDBACK:
            continue
        balance = sum(_outcome_value(item.outcome) for item in attributed.values()) / len(
            attributed
        )
        cap = max(0.0, weights.feedback_cap)
        signals[candidate.candidate_id] = max(-cap, min(cap, weights.feedback * balance))
    return signals


def _outcome_value(outcome: str) -> float:
    normalized = outcome.casefold()
    if normalized in _POSITIVE_OUTCOMES:
        return 1.0
    if normalized in _NEGATIVE_OUTCOMES:
        return -1.0
    return 0.0


def _ranking_quality(signals: Mapping[str, float], cap: float) -> float:
    if not signals:
        return 0.0
    value = sum(signals.values()) / len(signals)
    return max(-cap, min(cap, value))


def _duplicate_of(
    candidate: MemoryCandidate,
    selected: Sequence[MemoryCandidate],
    threshold: float,
) -> str | None:
    terms = _terms(candidate.index_text)
    for other in selected:
        other_terms = _terms(other.index_text)
        union = terms | other_terms
        similarity = len(terms & other_terms) / len(union) if union else 1.0
        if similarity >= threshold:
            return other.candidate_id
    return None


def _lexical_overlap(query: str, document: str) -> float:
    query_terms = _terms(query)
    if not query_terms:
        return 0.0
    return len(query_terms & _terms(document)) / len(query_terms)


def _terms(text: str) -> set[str]:
    return {
        normalized
        for match in _TOKEN_PATTERN.finditer(text)
        if (normalized := _normalize_term(match.group(0))) not in _STOP_TOKENS
    }


def _normalize_term(term: str) -> str:
    normalized = term.casefold()
    if len(normalized) > _PLURAL_STEM_LENGTH and normalized.endswith("s"):
        return normalized[:-1]
    return normalized


def _unit(value: float) -> float:
    return min(1.0, max(0.0, value))


def _evidence_precedence(candidate: MemoryCandidate) -> int:
    if candidate.evidence_class == "correction":
        return 2
    if candidate.evidence_class == "explicit":
        return 1
    return 0
