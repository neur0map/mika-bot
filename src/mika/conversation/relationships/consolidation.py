"""Pure consolidation of traceable claims into rollback-safe relationship profiles."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from mika.conversation.relationships.activation import ActivationPolicy
from mika.conversation.relationships.contracts import RelationshipClaim
from mika.conversation.relationships.extraction import EvidenceProposal
from mika.conversation.relationships.profile import ProfileEntry, RelationshipProfile

_INFERENCE_EXPIRY = timedelta(days=30)
_TERMINAL_STATES = frozenset({"superseded", "expired"})


@dataclass(frozen=True, slots=True)
class ConsolidationResult:
    """A consolidation outcome that callers can publish or retain safely."""

    profile: RelationshipProfile | None
    claims: tuple[RelationshipClaim, ...]
    changed: bool
    rejected: bool
    rollback_safe: bool
    salvaged_claim_ids: tuple[str, ...] = ()
    rejection_reason: str | None = None


class RelationshipConsolidator:
    """Build deterministic profiles while retaining protected predecessor evidence."""

    def __init__(self, activation_policy: ActivationPolicy | None = None) -> None:
        """Configure the pure activation policy used for candidate promotion."""
        self._activation_policy = activation_policy or ActivationPolicy()

    def consolidate(
        self,
        claims: Sequence[RelationshipClaim],
        evidence_by_key: Mapping[str, Sequence[EvidenceProposal]] | None = None,
        *,
        predecessor: RelationshipProfile | None = None,
        now: datetime,
    ) -> ConsolidationResult:
        """Return a promoted, merged, and predecessor-safe profile result."""
        normalized = _normalize_claims(claims, evidence_by_key or {}, self._activation_policy, now)
        current = _supersede_predecessors(normalized)
        merged = _merge_duplicate_support(current)
        proposed = _profile_for_active_claims(current, predecessor, now)
        return _result_for_predecessor(proposed, merged, predecessor)


def _normalize_claims(
    claims: Sequence[RelationshipClaim],
    evidence_by_key: Mapping[str, Sequence[EvidenceProposal]],
    policy: ActivationPolicy,
    now: datetime,
) -> tuple[RelationshipClaim, ...]:
    normalized_evidence = _normalized_evidence(evidence_by_key)
    return tuple(
        _normalize_claim(claim, normalized_evidence.get(_normalized(claim.key), ()), policy, now)
        for claim in claims
    )


def _normalized_evidence(
    evidence_by_key: Mapping[str, Sequence[EvidenceProposal]],
) -> dict[str, tuple[EvidenceProposal, ...]]:
    grouped: dict[str, list[EvidenceProposal]] = defaultdict(list)
    for key, evidence in evidence_by_key.items():
        grouped[_normalized(key)].extend(evidence)
    return {key: tuple(items) for key, items in grouped.items()}


def _normalize_claim(
    claim: RelationshipClaim,
    evidence: Sequence[EvidenceProposal],
    policy: ActivationPolicy,
    now: datetime,
) -> RelationshipClaim:
    normalized = replace(claim, key=_normalized(claim.key), value=_normalized_value(claim.value))
    decision = policy.evaluate(normalized, evidence)
    promoted = replace(
        normalized,
        state=decision.state,
        last_confirmed_at=now if decision.state == "active" else normalized.last_confirmed_at,
    )
    if _is_stale_inference(promoted, now):
        return replace(promoted, state="expired")
    return promoted


def _is_stale_inference(claim: RelationshipClaim, now: datetime) -> bool:
    return (
        claim.evidence_class == "inference"
        and claim.state == "candidate"
        and now - claim.last_observed_at > _INFERENCE_EXPIRY
    )


def _supersede_predecessors(claims: Sequence[RelationshipClaim]) -> tuple[RelationshipClaim, ...]:
    replacement_ids = {
        claim.predecessor_claim_id
        for claim in claims
        if claim.evidence_class == "correction" and claim.state == "active"
    }
    return tuple(
        replace(claim, state="superseded")
        if claim.claim_id in replacement_ids and claim.state not in _TERMINAL_STATES
        else claim
        for claim in claims
    )


def _merge_duplicate_support(claims: Sequence[RelationshipClaim]) -> tuple[RelationshipClaim, ...]:
    groups: dict[tuple[str, str, str, str], list[RelationshipClaim]] = defaultdict(list)
    for claim in claims:
        groups[_duplicate_key(claim)].append(claim)
    merged = [_merge_group(group) for group in groups.values()]
    return tuple(sorted(merged, key=lambda claim: claim.claim_id))


def _duplicate_key(claim: RelationshipClaim) -> tuple[str, str, str, str]:
    return (claim.subject_user_id, claim.kind, claim.key, claim.value)


def _merge_group(group: Sequence[RelationshipClaim]) -> RelationshipClaim:
    winner = min(group, key=_merge_preference)
    sources = tuple(sorted({source for claim in group for source in claim.source_message_ids}))
    return replace(
        winner,
        confidence=max(claim.confidence for claim in group),
        source_message_ids=sources,
        observation_count=len(sources),
        first_observed_at=min(claim.first_observed_at for claim in group),
        last_observed_at=max(claim.last_observed_at for claim in group),
    )


def _merge_preference(claim: RelationshipClaim) -> tuple[int, int, int, str]:
    precedence = {
        "correction": 0,
        "explicit": 1,
        "repeated_behavior": 2,
        "reaction": 3,
        "inference": 4,
    }
    state = 0 if claim.state == "active" else 1
    return (
        state,
        precedence[claim.evidence_class],
        -int(claim.last_observed_at.timestamp()),
        claim.claim_id,
    )


def _profile_for_active_claims(
    claims: Sequence[RelationshipClaim],
    predecessor: RelationshipProfile | None,
    now: datetime,
) -> RelationshipProfile | None:
    active = tuple(claim for claim in claims if claim.state == "active")
    if not active and predecessor is None:
        return None
    subject_user_id = _subject_user_id(active, predecessor)
    entries = _entries_for_claims(active)
    version = 1 if predecessor is None else predecessor.version + 1
    return _profile_from_entries(subject_user_id, version, entries)


def _subject_user_id(
    active: Sequence[RelationshipClaim], predecessor: RelationshipProfile | None
) -> str:
    if active:
        return active[0].subject_user_id
    assert predecessor is not None
    return predecessor.subject_user_id


def _entries_for_claims(
    claims: Sequence[RelationshipClaim],
) -> tuple[tuple[str, ProfileEntry], ...]:
    grouped: dict[tuple[str, str, str], list[RelationshipClaim]] = defaultdict(list)
    for claim in claims:
        grouped[(_profile_layer(claim), claim.key, claim.value)].append(claim)
    return tuple(
        (layer, _entry_for_group(group))
        for (layer, _, _), group in sorted(
            grouped.items(), key=lambda item: min(claim.first_observed_at for claim in item[1])
        )
    )


def _entry_for_group(group: Sequence[RelationshipClaim]) -> ProfileEntry:
    return ProfileEntry(
        key=group[0].key,
        value=group[0].value,
        claim_ids=tuple(sorted(claim.claim_id for claim in group)),
    )


def _profile_layer(claim: RelationshipClaim) -> str:
    if claim.kind in {"boundary", "conflict", "repair"} or claim.key.startswith("address:"):
        return "conflict_repair"
    if claim.kind == "expression":
        return "expression"
    if claim.kind == "preference":
        return "interests"
    if claim.kind in {"care", "support"}:
        return "care_patterns"
    if claim.kind in {"anchor", "event", "shared_moment"}:
        return "anchors"
    return "posture"


def _profile_from_entries(
    subject_user_id: str,
    version: int,
    entries: Sequence[tuple[str, ProfileEntry]],
) -> RelationshipProfile:
    by_layer: dict[str, list[ProfileEntry]] = defaultdict(list)
    for layer, entry in entries:
        by_layer[layer].append(entry)
    return RelationshipProfile(
        subject_user_id=subject_user_id,
        version=version,
        posture=tuple(by_layer["posture"]),
        expression=tuple(by_layer["expression"]),
        interests=tuple(by_layer["interests"]),
        care_patterns=tuple(by_layer["care_patterns"]),
        conflict_repair=tuple(by_layer["conflict_repair"]),
        anchors=tuple(by_layer["anchors"]),
    )


def _result_for_predecessor(
    proposed: RelationshipProfile | None,
    claims: tuple[RelationshipClaim, ...],
    predecessor: RelationshipProfile | None,
) -> ConsolidationResult:
    if predecessor is None:
        return ConsolidationResult(proposed, claims, proposed is not None, False, True)
    missing = _missing_protected_entries(proposed, claims, predecessor)
    if missing:
        safe_profile = _salvage_profile(proposed, predecessor, missing)
        return ConsolidationResult(
            safe_profile,
            claims,
            safe_profile.canonical_content() != predecessor.canonical_content(),
            True,
            True,
            _salvaged_claim_ids(proposed, predecessor),
            "protected_predecessor_claim_missing",
        )
    if proposed is not None and proposed.canonical_content() == predecessor.canonical_content():
        return ConsolidationResult(predecessor, claims, False, False, True)
    return ConsolidationResult(proposed, claims, proposed is not None, False, True)


def _missing_protected_entries(
    proposed: RelationshipProfile | None,
    claims: Sequence[RelationshipClaim],
    predecessor: RelationshipProfile,
) -> tuple[ProfileEntry, ...]:
    visible = (
        {claim_id for entry in proposed.entries for claim_id in entry.claim_ids}
        if proposed
        else set()
    )
    states = {claim.claim_id: claim.state for claim in claims}
    return tuple(
        entry
        for entry in predecessor.entries
        if any(states.get(claim_id) not in _TERMINAL_STATES for claim_id in entry.claim_ids)
        and not set(entry.claim_ids).issubset(visible)
    )


def _salvage_profile(
    proposed: RelationshipProfile | None,
    predecessor: RelationshipProfile,
    missing: Sequence[ProfileEntry],
) -> RelationshipProfile:
    current_entries = () if proposed is None else _layered_entries(proposed)
    safe_entries = (*current_entries, *(_entry_layer(predecessor, entry) for entry in missing))
    return _profile_from_entries(predecessor.subject_user_id, predecessor.version + 1, safe_entries)


def _layered_entries(profile: RelationshipProfile) -> tuple[tuple[str, ProfileEntry], ...]:
    return tuple((layer, entry) for layer, entries in _profile_layers(profile) for entry in entries)


def _entry_layer(profile: RelationshipProfile, entry: ProfileEntry) -> tuple[str, ProfileEntry]:
    return next(
        (layer, item)
        for layer, items in _profile_layers(profile)
        for item in items
        if item == entry
    )


def _profile_layers(
    profile: RelationshipProfile,
) -> tuple[tuple[str, tuple[ProfileEntry, ...]], ...]:
    return (
        ("posture", profile.posture),
        ("expression", profile.expression),
        ("interests", profile.interests),
        ("care_patterns", profile.care_patterns),
        ("conflict_repair", profile.conflict_repair),
        ("anchors", profile.anchors),
    )


def _salvaged_claim_ids(
    proposed: RelationshipProfile | None, predecessor: RelationshipProfile
) -> tuple[str, ...]:
    if proposed is None:
        return ()
    prior_ids = {claim_id for entry in predecessor.entries for claim_id in entry.claim_ids}
    return tuple(
        claim_id
        for entry in proposed.entries
        for claim_id in entry.claim_ids
        if claim_id not in prior_ids
    )


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _normalized_value(value: str) -> str:
    return " ".join(value.split())
