"""Pure mapping and scope helpers for relationship-memory orchestration."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from typing import cast

from mika.conversation.relationships.consolidation import RelationshipConsolidator
from mika.conversation.relationships.contracts import ClaimState, EvidenceClass, RelationshipClaim
from mika.conversation.relationships.extraction import EvidenceProposal, is_sensitive_evidence_text
from mika.conversation.relationships.profile import ProfileEntry, RelationshipProfile
from mika.conversation.relationships.service_contracts import ObservationInput
from mika.persistence.conversations.relationship_records import (
    ArchiveSourceRecord,
    ClaimEvidenceRecord,
    ClaimRecord,
    ClaimTransitionRecord,
    ClaimWrite,
    EvidenceWrite,
    ProfileClaimLinkRecord,
    ProfileVersionRecord,
)


def _claim_in_scope(
    claim: ClaimRecord,
    visibility_kind: str,
    guild_id: str | None,
    channel_id: str | None,
) -> bool:
    """Keep consolidation inputs within the exact requested retrieval scope."""
    if claim.visibility_kind == "global_explicit":
        return True
    if visibility_kind == "direct_message":
        return claim.visibility_kind == "direct_message" and claim.channel_id == channel_id
    if visibility_kind == "channel":
        return (
            claim.visibility_kind == "channel"
            and claim.guild_id == guild_id
            and claim.channel_id == channel_id
        )
    if visibility_kind == "guild":
        if claim.guild_id != guild_id:
            return False
        return claim.visibility_kind == "guild" or (
            claim.visibility_kind == "channel" and claim.channel_id == channel_id
        )
    return False


def _claim_write(
    claim_id: str,
    claim_key: str,
    predecessor_id: str | None,
    observation: ObservationInput,
    proposal: EvidenceProposal,
) -> ClaimWrite:
    return ClaimWrite(
        claim_id,
        observation.subject_user_id,
        observation.visibility_kind,
        observation.guild_id,
        observation.channel_id,
        proposal.kind,
        claim_key,
        proposal.value,
        proposal.evidence_class,
        proposal.confidence,
        "candidate",
        predecessor_id,
        observation.created_at,
    )


def _evidence_write(observation: ObservationInput, policy_version_id: str) -> EvidenceWrite:
    return EvidenceWrite(
        observation.source_kind,
        observation.source_id,
        observation.message_id,
        observation.created_at,
        observation.visibility_kind,
        observation.guild_id,
        observation.channel_id,
        policy_version_id,
    )


def _relationship_claim(record: ClaimRecord) -> RelationshipClaim:
    return RelationshipClaim(
        record.claim_id,
        record.subject_user_id,
        record.guild_id,
        record.channel_id,
        record.kind,
        record.key,
        record.value,
        cast(EvidenceClass, record.evidence_class),
        record.confidence,
        record.source_message_ids,
        record.observation_count,
        record.first_observed_at,
        record.last_observed_at,
        record.last_confirmed_at,
        cast(ClaimState, record.state),
        record.predecessor_claim_id,
    )


def _claim_transitions(
    records: Sequence[ClaimRecord],
    claims: Sequence[RelationshipClaim],
    transitioned_at: datetime,
) -> tuple[ClaimTransitionRecord, ...]:
    prior = {item.claim_id: item.state for item in records}
    return tuple(
        ClaimTransitionRecord(claim.claim_id, previous, claim.state, transitioned_at)
        for claim in claims
        if (previous := prior.get(claim.claim_id)) is not None and previous != claim.state
    )


def _relationship_profile(
    record: ProfileVersionRecord, claims: Sequence[ClaimRecord]
) -> RelationshipProfile:
    by_id = {claim.claim_id: claim for claim in claims}
    grouped: dict[tuple[str, int], list[ClaimRecord]] = defaultdict(list)
    for link in record.claim_links:
        claim = by_id.get(link.claim_id)
        if claim is None:
            raise ValueError("active relationship profile references an unknown claim")
        grouped[(link.layer, link.position)].append(claim)
    entries: dict[str, list[tuple[int, ProfileEntry]]] = defaultdict(list)
    for (layer, position), items in grouped.items():
        keys = {" ".join(item.key.casefold().split()) for item in items}
        values = {" ".join(item.value.split()) for item in items}
        if len(keys) != 1 or len(values) != 1:
            raise ValueError("active relationship profile claim group is inconsistent")
        entries[layer].append(
            (
                position,
                ProfileEntry(
                    next(iter(keys)),
                    next(iter(values)),
                    tuple(sorted(item.claim_id for item in items)),
                ),
            )
        )
    profile = RelationshipProfile(
        subject_user_id=record.subject_user_id,
        version=1,
        posture=_ordered_entries(entries["posture"]),
        expression=_ordered_entries(entries["expression"]),
        interests=_ordered_entries(entries["interests"]),
        care_patterns=_ordered_entries(entries["care_patterns"]),
        conflict_repair=_ordered_entries(entries["conflict_repair"]),
        anchors=_ordered_entries(entries["anchors"]),
    )
    if (profile.index_text, profile.overview_text) != (record.index_text, record.overview_text):
        raise ValueError("active relationship profile content does not match its claim links")
    return profile


def _predecessor_profile(
    record: ProfileVersionRecord | None,
    claims: Sequence[ClaimRecord],
    evidence_by_claim_id: Mapping[str, Sequence[EvidenceProposal]],
    now: datetime,
) -> RelationshipProfile | None:
    if record is None:
        return None
    if record.claim_links or not (record.index_text.strip() or record.overview_text.strip()):
        return _relationship_profile(record, claims)
    rebuilt = (
        RelationshipConsolidator()
        .consolidate(
            tuple(_relationship_claim(claim) for claim in claims),
            evidence_by_claim_id=evidence_by_claim_id,
            now=now,
        )
        .profile
    )
    if rebuilt is None or (rebuilt.index_text, rebuilt.overview_text) != (
        record.index_text,
        record.overview_text,
    ):
        raise ValueError("legacy relationship profile cannot be reconstructed from claim history")
    return rebuilt


def _profile_claim_links(profile: RelationshipProfile) -> tuple[ProfileClaimLinkRecord, ...]:
    layers = (
        ("posture", profile.posture),
        ("expression", profile.expression),
        ("interests", profile.interests),
        ("care_patterns", profile.care_patterns),
        ("conflict_repair", profile.conflict_repair),
        ("anchors", profile.anchors),
    )
    return tuple(
        ProfileClaimLinkRecord(claim_id, layer, position)
        for layer, layer_entries in layers
        for position, entry in enumerate(layer_entries)
        for claim_id in entry.claim_ids
    )


def _profile_link_key(link: ProfileClaimLinkRecord) -> tuple[str, int, str]:
    return (link.layer, link.position, link.claim_id)


def _ordered_entries(entries: Sequence[tuple[int, ProfileEntry]]) -> tuple[ProfileEntry, ...]:
    return tuple(entry for _, entry in sorted(entries, key=lambda item: item[0]))


def _proposal_from_record(record: ClaimEvidenceRecord, claim: ClaimRecord) -> EvidenceProposal:
    return EvidenceProposal(
        claim.kind,
        claim.key,
        claim.value,
        cast(EvidenceClass, claim.evidence_class),
        claim.confidence,
        record.source_message_id,
        record.source_timestamp,
        "stored_evidence",
    )


def _evidence_by_claim(
    claims: Sequence[ClaimRecord], evidence: Sequence[ClaimEvidenceRecord]
) -> Mapping[str, Sequence[EvidenceProposal]]:
    by_id = {item.claim_id: item for item in claims}
    grouped: dict[str, list[EvidenceProposal]] = defaultdict(list)
    for item in evidence:
        claim = by_id.get(item.claim_id)
        if claim is not None:
            grouped[item.claim_id].append(_proposal_from_record(item, claim))
    return grouped


def _correction_predecessor(
    claims: Sequence[ClaimRecord],
    proposal: EvidenceProposal,
    observation: ObservationInput,
) -> ClaimRecord | None:
    if proposal.evidence_class != "correction":
        return None
    normalized_key = " ".join(proposal.key.casefold().split())
    candidates = [
        item
        for item in claims
        if (
            item.state == "active"
            or (item.state == "candidate" and item.last_observed_at <= proposal.source_timestamp)
        )
        and item.subject_user_id == observation.subject_user_id
        and item.kind == proposal.kind
        and " ".join(item.key.casefold().split()) == normalized_key
        and item.value != proposal.value
        and item.visibility_kind == observation.visibility_kind
        and item.guild_id == observation.guild_id
        and item.channel_id == observation.channel_id
    ]
    return max(candidates, key=lambda item: item.last_observed_at) if candidates else None


def _claim_id(observation: ObservationInput, proposal: EvidenceProposal) -> str:
    return _stable_id(
        "claim",
        observation.subject_user_id,
        observation.visibility_kind,
        observation.guild_id or "",
        observation.channel_id or "",
        proposal.kind,
        proposal.key,
        proposal.value,
        proposal.evidence_class,
    )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256(chr(0).join(parts).encode()).hexdigest()
    return f"{prefix}-{digest[:24]}"


def _visibility_allowed(rules: Mapping[str, bool], visibility_kind: str) -> bool:
    """Preserve legacy policies while enforcing explicit runtime scope switches."""
    return rules.get(visibility_kind, True)


def _physical_archive_visibility(source: ArchiveSourceRecord) -> str:
    if source.guild_id is not None and source.channel_id is not None:
        return "channel"
    if source.guild_id is not None:
        return "guild"
    return "direct_message"


def _effective_archive_observation(
    source: ArchiveSourceRecord,
    observation: ObservationInput,
    proposal: EvidenceProposal,
) -> ObservationInput:
    trusted_global = (
        source.visibility_kind == "global_explicit"
        and proposal.evidence_class in {"explicit", "correction"}
        and not is_sensitive_evidence_text(source.text)
    )
    if trusted_global:
        return observation
    return replace(observation, visibility_kind=_physical_archive_visibility(source))
