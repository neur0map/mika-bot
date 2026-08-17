"""Deterministic activation thresholds for relationship claims."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mika.conversation.relationships import EvidenceClass, RelationshipClaim
from mika.conversation.relationships.activation import ActivationPolicy
from mika.conversation.relationships.extraction import EvidenceProposal

BASE_TIME = datetime(2026, 8, 17, 10, tzinfo=UTC)


def claim(evidence_class: EvidenceClass) -> RelationshipClaim:
    """Create a candidate claim for one evidence category."""
    return RelationshipClaim(
        claim_id="claim-1",
        subject_user_id="user-1",
        guild_id="guild-1",
        channel_id="channel-1",
        kind="preference",
        key="preference:tea",
        value="tea",
        evidence_class=evidence_class,
        confidence=0.8,
        source_message_ids=("message-0",),
        observation_count=1,
        first_observed_at=BASE_TIME,
        last_observed_at=BASE_TIME,
        last_confirmed_at=None,
    )


def evidence(
    evidence_class: EvidenceClass,
    source_id: str,
    observed_at: datetime,
    *,
    value: str = "tea",
) -> EvidenceProposal:
    """Create traceable evidence without persistence dependencies."""
    return EvidenceProposal(
        kind="preference",
        key="preference:tea",
        value=value,
        evidence_class=evidence_class,
        confidence=0.8,
        source_message_id=source_id,
        source_timestamp=observed_at,
        reason="test",
    )


def test_explicit_fact_activates_immediately() -> None:
    """A direct user fact needs no behavioral corroboration."""
    decision = ActivationPolicy().evaluate(
        claim("explicit"), [evidence("explicit", "message-1", BASE_TIME)]
    )

    assert decision.state == "active"
    assert decision.reason == "explicit_fact"


def test_explicit_evidence_outranks_a_behavior_candidate() -> None:
    """A later direct fact must promote the same claim over weaker behavior."""
    decision = ActivationPolicy().evaluate(
        claim("repeated_behavior"),
        [evidence("explicit", "message-1", BASE_TIME)],
    )

    assert decision.state == "active"
    assert decision.reason == "explicit_fact"


def test_direct_correction_activates_immediately() -> None:
    """Corrections become usable as soon as their source is retained."""
    decision = ActivationPolicy().evaluate(
        claim("correction"), [evidence("correction", "message-1", BASE_TIME)]
    )

    assert decision.state == "active"
    assert decision.reason == "direct_correction"


def test_behavior_requires_three_observations_across_two_days() -> None:
    """One-day repetition remains candidate evidence."""
    policy = ActivationPolicy()
    candidate = claim("repeated_behavior")

    one_day = policy.evaluate(
        candidate,
        [
            evidence("repeated_behavior", "message-1", BASE_TIME),
            evidence("repeated_behavior", "message-2", BASE_TIME + timedelta(hours=1)),
            evidence("repeated_behavior", "message-3", BASE_TIME + timedelta(hours=2)),
        ],
    )
    active = policy.evaluate(
        candidate,
        [
            evidence("repeated_behavior", "message-1", BASE_TIME),
            evidence("repeated_behavior", "message-2", BASE_TIME + timedelta(days=1)),
            evidence("repeated_behavior", "message-3", BASE_TIME + timedelta(days=1, hours=1)),
        ],
    )

    assert one_day.state == "candidate"
    assert one_day.reason == "behavior_needs_three_observations_across_two_days"
    assert active.state == "active"
    assert active.reason == "behavior_threshold_met"


def test_reaction_requires_three_consistent_positive_signals() -> None:
    """Reaction support is activated only when signals agree."""
    candidate = claim("reaction")
    policy = ActivationPolicy()

    inconsistent = policy.evaluate(
        candidate,
        [
            evidence("reaction", "message-1", BASE_TIME),
            evidence("reaction", "message-2", BASE_TIME + timedelta(days=1)),
            evidence("reaction", "message-3", BASE_TIME + timedelta(days=2), value="negative"),
        ],
    )
    active = policy.evaluate(
        candidate,
        [
            evidence("reaction", "message-1", BASE_TIME),
            evidence("reaction", "message-2", BASE_TIME + timedelta(days=1)),
            evidence("reaction", "message-3", BASE_TIME + timedelta(days=2)),
        ],
    )

    assert inconsistent.state == "candidate"
    assert inconsistent.reason == "reaction_signals_inconsistent"
    assert active.state == "active"
    assert active.reason == "reaction_threshold_met"


def test_negative_reaction_outranks_a_positive_signal_from_the_same_source() -> None:
    """Source deduplication must not hide a conflicting negative reaction."""
    decision = ActivationPolicy().evaluate(
        claim("reaction"),
        [
            evidence("reaction", "message-1", BASE_TIME),
            evidence("reaction", "message-1", BASE_TIME, value="negative"),
            evidence("reaction", "message-2", BASE_TIME + timedelta(days=1)),
            evidence("reaction", "message-3", BASE_TIME + timedelta(days=2)),
        ],
    )

    assert decision.state == "candidate"
    assert decision.reason == "reaction_signals_inconsistent"


def test_inference_remains_a_candidate() -> None:
    """Unverified inference cannot become prompt-visible memory."""
    decision = ActivationPolicy().evaluate(
        claim("inference"),
        [
            evidence("inference", f"message-{index}", BASE_TIME + timedelta(days=index))
            for index in range(5)
        ],
    )

    assert decision.state == "candidate"
    assert decision.reason == "inference_requires_corroboration"


def test_correction_evidence_outranks_behavioral_support() -> None:
    """A direct correction takes precedence over every weaker evidence class."""
    decision = ActivationPolicy().evaluate(
        claim("repeated_behavior"),
        [
            evidence("repeated_behavior", "message-1", BASE_TIME),
            evidence("correction", "message-2", BASE_TIME + timedelta(hours=1)),
        ],
    )

    assert decision.state == "active"
    assert decision.reason == "direct_correction"
