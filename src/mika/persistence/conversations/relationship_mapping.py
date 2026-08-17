"""Translate relationship-memory DTOs to and from normalized ORM rows."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mika.persistence.conversations.relationship_models import (
    StoredClaim,
    StoredClaimEvidence,
    StoredPolicyVersion,
    StoredProfileVersion,
    StoredRecallEvent,
)
from mika.persistence.conversations.relationship_records import (
    ClaimRecord,
    ClaimWrite,
    EvidenceWrite,
    ProfileVersionRecord,
    RecallEventWrite,
    RelationshipMemoryPolicyVersionRecord,
)


async def claim_record(session: AsyncSession, stored: StoredClaim) -> ClaimRecord:
    """Build a claim record with its ordered, deduplicated source summary."""
    source_ids = tuple(
        (
            await session.scalars(
                select(StoredClaimEvidence.source_message_id)
                .where(StoredClaimEvidence.claim_id == stored.claim_id)
                .order_by(StoredClaimEvidence.source_message_id)
            )
        ).all()
    )
    return ClaimRecord(
        claim_id=stored.claim_id,
        subject_user_id=stored.subject_user_id,
        visibility_kind=stored.visibility_kind,
        guild_id=stored.guild_id,
        channel_id=stored.channel_id,
        kind=stored.kind,
        key=stored.key,
        value=stored.value,
        evidence_class=stored.evidence_class,
        confidence=stored.confidence,
        state=stored.state,
        predecessor_claim_id=stored.predecessor_claim_id,
        source_message_ids=source_ids,
        observation_count=len(source_ids),
        first_observed_at=stored.first_observed_at,
        last_observed_at=stored.last_observed_at,
        last_confirmed_at=stored.last_confirmed_at,
    )


def stored_claim(claim: ClaimWrite) -> StoredClaim:
    """Create an unsaved ORM claim from a primitive write record."""
    observed_at = as_utc(claim.observed_at)
    return StoredClaim(
        claim_id=claim.claim_id,
        subject_user_id=claim.subject_user_id,
        visibility_kind=claim.visibility_kind,
        guild_id=claim.guild_id,
        channel_id=claim.channel_id,
        kind=claim.kind,
        key=claim.key,
        value=claim.value,
        evidence_class=claim.evidence_class,
        confidence=claim.confidence,
        state=claim.state,
        predecessor_claim_id=claim.predecessor_claim_id,
        first_observed_at=observed_at,
        last_observed_at=observed_at,
        last_confirmed_at=None,
    )


def stored_evidence(claim_id: str, evidence: EvidenceWrite) -> StoredClaimEvidence:
    """Create an unsaved ORM evidence row without transcript content."""
    return StoredClaimEvidence(
        claim_id=claim_id,
        source_kind=evidence.source_kind,
        source_id=evidence.source_id,
        source_message_id=evidence.source_message_id,
        source_timestamp=evidence.source_timestamp,
        visibility_kind=evidence.visibility_kind,
        guild_id=evidence.guild_id,
        channel_id=evidence.channel_id,
        policy_version_id=evidence.policy_version_id,
    )


def same_claim(stored: StoredClaim, claim: ClaimWrite) -> bool:
    """Check whether a reused ID still names the same immutable truth fields."""
    return (
        stored.subject_user_id,
        stored.visibility_kind,
        stored.guild_id,
        stored.channel_id,
        stored.kind,
        stored.key,
        stored.value,
        stored.evidence_class,
        stored.confidence,
        stored.predecessor_claim_id,
    ) == (
        claim.subject_user_id,
        claim.visibility_kind,
        claim.guild_id,
        claim.channel_id,
        claim.kind,
        claim.key,
        claim.value,
        claim.evidence_class,
        claim.confidence,
        claim.predecessor_claim_id,
    )


def profile_record(stored: StoredProfileVersion) -> ProfileVersionRecord:
    """Convert one immutable profile ORM row to its DTO."""
    return ProfileVersionRecord(
        stored.profile_version_id,
        stored.subject_user_id,
        stored.index_text,
        stored.overview_text,
        stored.schema_version,
        stored.generator_version,
        stored.policy_version_id,
        stored.created_at,
    )


def policy_record(stored: StoredPolicyVersion) -> RelationshipMemoryPolicyVersionRecord:
    """Convert and validate one immutable policy ORM row."""
    rules = json.loads(stored.visibility_rules_json)
    if not isinstance(rules, dict) or not all(
        isinstance(key, str) and isinstance(value, bool) for key, value in rules.items()
    ):
        raise ValueError("stored relationship-memory visibility rules are invalid")
    return RelationshipMemoryPolicyVersionRecord(
        stored.policy_version_id,
        stored.relationship_learning_enabled,
        stored.semantic_retrieval_enabled,
        stored.provider_extraction_enabled,
        stored.local_relation_model_enabled,
        rules,
        stored.change_reason,
        stored.created_at,
    )


def recall_values(event: RecallEventWrite) -> dict[str, object]:
    """Serialize content-free recall metadata deterministically."""
    return {
        "recall_event_id": event.recall_event_id,
        "subject_user_id": event.subject_user_id,
        "visibility_kind": event.visibility_kind,
        "guild_id": event.guild_id,
        "channel_id": event.channel_id,
        "query_hash": event.query_hash,
        "relation_label": event.relation_label,
        "candidate_ids_json": canonical_json(event.candidate_ids),
        "selected_claim_ids_json": canonical_json(event.selected_claim_ids),
        "selected_tiers_json": canonical_json(event.selected_tiers),
        "rejection_reasons_json": canonical_json(event.rejection_reasons),
        "estimated_token_cost": event.estimated_token_cost,
        "latency_ms": event.latency_ms,
        "retrieval_version": event.retrieval_version,
        "policy_version_id": event.policy_version_id,
        "created_at": as_utc(event.created_at),
    }


def stored_recall_values(stored: StoredRecallEvent) -> dict[str, object]:
    """Return the serialized fields used to enforce recall idempotency."""
    return {
        column: getattr(stored, column)
        for column in (
            "recall_event_id",
            "subject_user_id",
            "visibility_kind",
            "guild_id",
            "channel_id",
            "query_hash",
            "relation_label",
            "candidate_ids_json",
            "selected_claim_ids_json",
            "selected_tiers_json",
            "rejection_reasons_json",
            "estimated_token_cost",
            "latency_ms",
            "retrieval_version",
            "policy_version_id",
            "created_at",
        )
    }


def canonical_json(value: object) -> str:
    """Serialize primitive containers using stable JSON."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def as_utc(value: datetime) -> datetime:
    """Normalize an aware timestamp or reject ambiguous input."""
    if value.tzinfo is None:
        raise ValueError("relationship-memory timestamps must be timezone-aware")
    return value.astimezone(UTC)
