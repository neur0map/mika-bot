"""Short-session adapter for relationship-memory runtime operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from mika.persistence.conversations.relationship_memory import RelationshipMemoryRepository
from mika.persistence.conversations.relationship_records import (
    ArchiveCursor,
    ClaimEvidenceRecord,
    ClaimRecord,
    ClaimTransitionRecord,
    ClaimWrite,
    EvidenceWrite,
    ProfileVersionRecord,
    RecallEventWrite,
    RelationshipMemoryPolicyVersionRecord,
)
from mika.persistence.engine import session


class ManagedRelationshipMemory:
    """Open an isolated ORM session for each concurrent runtime operation."""

    async def ensure_policy_version(
        self, record: RelationshipMemoryPolicyVersionRecord
    ) -> RelationshipMemoryPolicyVersionRecord:
        """Publish policy settings only when their effective content changes."""
        async with session() as active:
            repository = RelationshipMemoryRepository(active)
            current = await repository.active_policy_version()
            if current is not None and _policy_content(current) == _policy_content(record):
                return current
            await repository.write_policy_version(record)
            return record

    async def active_policy_version(self) -> RelationshipMemoryPolicyVersionRecord | None:
        async with session() as active:
            return await RelationshipMemoryRepository(active).active_policy_version()

    async def last_consolidated_at(self, subject_user_id: str) -> datetime | None:
        async with session() as active:
            return await RelationshipMemoryRepository(active).last_consolidated_at(subject_user_id)

    async def scoped_last_consolidated_at(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> datetime | None:
        async with session() as active:
            return await RelationshipMemoryRepository(active).scoped_last_consolidated_at(
                subject_user_id,
                visibility_kind=visibility_kind,
                guild_id=guild_id,
                channel_id=channel_id,
            )

    async def record_consolidated_at(self, subject_user_id: str, completed_at: datetime) -> None:
        async with session() as active:
            await RelationshipMemoryRepository(active).record_consolidated_at(
                subject_user_id, completed_at
            )

    async def record_scoped_consolidated_at(
        self,
        subject_user_id: str,
        completed_at: datetime,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> None:
        async with session() as active:
            await RelationshipMemoryRepository(active).record_scoped_consolidated_at(
                subject_user_id,
                completed_at,
                visibility_kind=visibility_kind,
                guild_id=guild_id,
                channel_id=channel_id,
            )

    async def add_evidence(self, claim: ClaimWrite, evidence: EvidenceWrite) -> ClaimRecord:
        async with session() as active:
            return await RelationshipMemoryRepository(active).add_evidence(claim, evidence)

    async def activate_claim(self, claim_id: str, *, confirmed_at: datetime) -> ClaimRecord:
        async with session() as active:
            return await RelationshipMemoryRepository(active).activate_claim(
                claim_id, confirmed_at=confirmed_at
            )

    async def claims_for_user(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
        limit: int = 100,
    ) -> list[ClaimRecord]:
        async with session() as active:
            return await RelationshipMemoryRepository(active).claims_for_user(
                subject_user_id,
                visibility_kind=visibility_kind,
                guild_id=guild_id,
                channel_id=channel_id,
                limit=limit,
            )

    async def claims_for_subject(self, subject_user_id: str) -> list[ClaimRecord]:
        async with session() as active:
            return await RelationshipMemoryRepository(active).claims_for_subject(subject_user_id)

    async def evidence_for_claims(self, claim_ids: Sequence[str]) -> list[ClaimEvidenceRecord]:
        async with session() as active:
            return await RelationshipMemoryRepository(active).evidence_for_claims(claim_ids)

    async def active_profile_for_scope(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> ProfileVersionRecord | None:
        async with session() as active:
            return await RelationshipMemoryRepository(active).active_profile_for_scope(
                subject_user_id,
                visibility_kind=visibility_kind,
                guild_id=guild_id,
                channel_id=channel_id,
            )

    async def active_profiles_for_subject(self, subject_user_id: str) -> list[ProfileVersionRecord]:
        async with session() as active:
            return await RelationshipMemoryRepository(active).active_profiles_for_subject(
                subject_user_id
            )

    async def write_profile_version(self, record: ProfileVersionRecord) -> None:
        async with session() as active:
            await RelationshipMemoryRepository(active).write_profile_version(record)

    async def publish_consolidation(
        self,
        record: ProfileVersionRecord | None,
        transitions: Sequence[ClaimTransitionRecord],
    ) -> None:
        async with session() as active:
            await RelationshipMemoryRepository(active).publish_consolidation(record, transitions)

    async def record_recall(self, event: RecallEventWrite) -> None:
        async with session() as active:
            await RelationshipMemoryRepository(active).record_recall(event)

    async def cursor(self, source_name: str) -> ArchiveCursor | None:
        async with session() as active:
            return await RelationshipMemoryRepository(active).cursor(source_name)

    async def advance_cursor(self, cursor: ArchiveCursor) -> None:
        async with session() as active:
            await RelationshipMemoryRepository(active).advance_cursor(cursor)


def _policy_content(record: RelationshipMemoryPolicyVersionRecord) -> tuple[object, ...]:
    rules: Mapping[str, bool] = record.visibility_rules
    return (
        record.relationship_learning_enabled,
        record.semantic_retrieval_enabled,
        record.provider_extraction_enabled,
        record.local_relation_model_enabled,
        tuple(sorted(rules.items())),
    )
