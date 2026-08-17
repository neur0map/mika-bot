"""Pure, deterministic activation rules for relationship-memory claims."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from mika.conversation.relationships.contracts import ClaimState, RelationshipClaim
from mika.conversation.relationships.extraction import EvidenceProposal

_BEHAVIOR_OBSERVATION_MINIMUM = 3
_BEHAVIOR_DAY_MINIMUM = 2
_REACTION_SIGNAL_MINIMUM = 3


@dataclass(frozen=True, slots=True)
class ActivationDecision:
    """The lifecycle result and traceable reason for one claim evaluation."""

    state: ClaimState
    reason: str


class ActivationPolicy:
    """Promote claims only when their evidence class meets a literal threshold."""

    def evaluate(
        self,
        claim: RelationshipClaim,
        evidence: Sequence[EvidenceProposal],
    ) -> ActivationDecision:
        """Return an activation decision without mutating claim or evidence state."""
        if claim.state != "candidate":
            return ActivationDecision(claim.state, "claim_not_candidate")

        supporting = tuple(item for item in evidence if item.key == claim.key)
        if _has_class(supporting, "correction"):
            return ActivationDecision("active", "direct_correction")
        if _has_class(supporting, "explicit"):
            return ActivationDecision("active", "explicit_fact")
        if claim.evidence_class == "repeated_behavior":
            return _behavior_decision(supporting)
        if claim.evidence_class == "reaction":
            return _reaction_decision(claim, supporting)
        return ActivationDecision("candidate", "inference_requires_corroboration")


def _has_class(evidence: Sequence[EvidenceProposal], evidence_class: str) -> bool:
    """Require at least one source-backed observation of an evidence class."""
    return any(item.evidence_class == evidence_class for item in evidence)


def _behavior_decision(evidence: Sequence[EvidenceProposal]) -> ActivationDecision:
    """Activate behavior only from three source-distinct observations over two days."""
    observations = _distinct_by_source(evidence, "repeated_behavior")
    days = {item.source_timestamp.date() for item in observations}
    if len(observations) >= _BEHAVIOR_OBSERVATION_MINIMUM and len(days) >= _BEHAVIOR_DAY_MINIMUM:
        return ActivationDecision("active", "behavior_threshold_met")
    return ActivationDecision("candidate", "behavior_needs_three_observations_across_two_days")


def _reaction_decision(
    claim: RelationshipClaim,
    evidence: Sequence[EvidenceProposal],
) -> ActivationDecision:
    """Activate reaction evidence only when three source-distinct signals agree."""
    if any(item.evidence_class == "reaction" and item.value == "negative" for item in evidence):
        return ActivationDecision("candidate", "reaction_signals_inconsistent")
    reactions = _distinct_by_source(evidence, "reaction")
    consistent = [item for item in reactions if item.value == claim.value]
    if len(consistent) >= _REACTION_SIGNAL_MINIMUM:
        return ActivationDecision("active", "reaction_threshold_met")
    return ActivationDecision("candidate", "reaction_needs_three_consistent_signals")


def _distinct_by_source(
    evidence: Sequence[EvidenceProposal],
    evidence_class: str,
) -> tuple[EvidenceProposal, ...]:
    """Deduplicate repeated processing of the same source message."""
    seen: set[str] = set()
    distinct: list[EvidenceProposal] = []
    for item in evidence:
        if item.evidence_class != evidence_class or item.source_message_id in seen:
            continue
        seen.add(item.source_message_id)
        distinct.append(item)
    return tuple(distinct)
