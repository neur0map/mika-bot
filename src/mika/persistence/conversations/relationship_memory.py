"""Transactional persistence operations for relationship memory."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from mika.persistence.conversations.relationship_mapping import (
    as_utc,
    canonical_json,
    claim_record,
    policy_record,
    profile_record,
    recall_values,
    same_claim,
    stored_claim,
    stored_evidence,
    stored_recall_values,
)
from mika.persistence.conversations.relationship_models import (
    StoredArchiveCursor,
    StoredClaim,
    StoredClaimEvidence,
    StoredPolicyHead,
    StoredPolicyVersion,
    StoredProfileHead,
    StoredProfileVersion,
    StoredRecallEvent,
    StoredRecallFeedback,
    StoredRecallFeedbackClaim,
)
from mika.persistence.conversations.relationship_records import (
    ArchiveCursor,
    ArchiveSourceRecord,
    ClaimRecord,
    ClaimWrite,
    EvidenceWrite,
    ProfileVersionRecord,
    RecallEventWrite,
    RecallFeedbackWrite,
    RelationshipMemoryPolicyVersionRecord,
)
from mika.persistence.conversations.social_models import UserFact


class RelationshipMemoryRepository:
    """Persist relationship evidence, versions, cursors, and recall attribution."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """Expose the owned session for aggregate persistence queries."""
        return self._session

    async def close(self) -> None:
        """Close the repository's database session."""
        await self._session.close()

    async def add_evidence(self, claim: ClaimWrite, evidence: EvidenceWrite) -> ClaimRecord:
        """Create a claim if needed and attach one deduplicated source observation."""
        stored = await self._session.get(StoredClaim, claim.claim_id)
        if stored is None:
            stored = stored_claim(claim)
            self._session.add(stored)
            await self._session.flush()
        elif not same_claim(stored, claim):
            await self._session.rollback()
            raise ValueError("claim id is already bound to different truth fields")
        statement = select(StoredClaimEvidence.id).where(
            StoredClaimEvidence.claim_id == claim.claim_id,
            StoredClaimEvidence.source_kind == evidence.source_kind,
            StoredClaimEvidence.source_id == evidence.source_id,
        )
        if (await self._session.scalar(statement)) is None:
            self._session.add(stored_evidence(claim.claim_id, evidence))
            stored.first_observed_at = min(stored.first_observed_at, evidence.source_timestamp)
            stored.last_observed_at = max(stored.last_observed_at, evidence.source_timestamp)
        await self._commit()
        return await claim_record(self._session, stored)

    async def activate_claim(self, claim_id: str, *, confirmed_at: datetime) -> ClaimRecord:
        """Activate an existing claim and record its confirmation time."""
        stored = await self._require_claim(claim_id)
        stored.state = "active"
        stored.last_confirmed_at = as_utc(confirmed_at)
        await self._commit()
        return await claim_record(self._session, stored)

    async def supersede_claim(
        self,
        previous_claim_id: str,
        replacement: ClaimWrite,
        evidence: EvidenceWrite,
        *,
        superseded_at: datetime,
    ) -> ClaimRecord:
        """Atomically retain an old claim and activate its correction."""
        previous = await self._require_claim(previous_claim_id)
        if await self._session.get(StoredClaim, replacement.claim_id) is not None:
            await self._session.rollback()
            raise ValueError("replacement claim already exists")
        if replacement.predecessor_claim_id != previous_claim_id:
            await self._session.rollback()
            raise ValueError("replacement predecessor does not match superseded claim")
        previous.state = "superseded"
        previous.last_observed_at = max(previous.last_observed_at, as_utc(superseded_at))
        stored = stored_claim(replacement)
        stored.state = "active"
        stored.last_confirmed_at = as_utc(superseded_at)
        self._session.add_all([stored, stored_evidence(replacement.claim_id, evidence)])
        await self._commit()
        return await claim_record(self._session, stored)

    async def claim(self, claim_id: str) -> ClaimRecord | None:
        """Return one claim for audit operations."""
        stored = await self._session.get(StoredClaim, claim_id)
        return None if stored is None else await claim_record(self._session, stored)

    async def claims_for_user(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
        limit: int = 100,
    ) -> list[ClaimRecord]:
        """Return active claims visible in the supplied conversation scope."""
        scopes = [StoredClaim.visibility_kind == "global_explicit"]
        if visibility_kind == "direct_message":
            scopes.append(
                (StoredClaim.visibility_kind == "direct_message")
                & (StoredClaim.channel_id == channel_id)
            )
        else:
            scopes.append(
                (StoredClaim.visibility_kind == "guild") & (StoredClaim.guild_id == guild_id)
            )
            scopes.append(
                (StoredClaim.visibility_kind == "channel")
                & (StoredClaim.guild_id == guild_id)
                & (StoredClaim.channel_id == channel_id)
            )
        statement = (
            select(StoredClaim)
            .where(
                StoredClaim.subject_user_id == subject_user_id,
                StoredClaim.state == "active",
                or_(*scopes),
            )
            .order_by(StoredClaim.last_confirmed_at.desc(), StoredClaim.claim_id)
            .limit(limit)
        )
        return [
            await claim_record(self._session, row)
            for row in (await self._session.scalars(statement)).all()
        ]

    async def write_profile_version(self, record: ProfileVersionRecord) -> None:
        """Insert an immutable profile version and atomically move its user's head."""
        if await self._session.get(StoredProfileVersion, record.profile_version_id) is not None:
            await self._session.rollback()
            raise ValueError("profile version already exists")
        self._session.add(
            StoredProfileVersion(
                profile_version_id=record.profile_version_id,
                subject_user_id=record.subject_user_id,
                index_text=record.index_text,
                overview_text=record.overview_text,
                schema_version=record.schema_version,
                generator_version=record.generator_version,
                policy_version_id=record.policy_version_id,
                created_at=record.created_at,
            )
        )
        head = await self._session.get(StoredProfileHead, record.subject_user_id)
        if head is None:
            self._session.add(
                StoredProfileHead(
                    subject_user_id=record.subject_user_id,
                    profile_version_id=record.profile_version_id,
                )
            )
        else:
            head.profile_version_id = record.profile_version_id
        await self._commit()

    async def active_profile(self, subject_user_id: str) -> ProfileVersionRecord | None:
        """Return the active immutable profile for one user."""
        statement = (
            select(StoredProfileVersion)
            .join(
                StoredProfileHead,
                StoredProfileHead.profile_version_id == StoredProfileVersion.profile_version_id,
            )
            .where(StoredProfileHead.subject_user_id == subject_user_id)
        )
        stored = await self._session.scalar(statement)
        return None if stored is None else profile_record(stored)

    async def write_policy_version(self, record: RelationshipMemoryPolicyVersionRecord) -> None:
        """Insert an immutable policy version and atomically make it effective."""
        if await self._session.get(StoredPolicyVersion, record.policy_version_id) is not None:
            await self._session.rollback()
            raise ValueError("policy version already exists")
        self._session.add(
            StoredPolicyVersion(
                policy_version_id=record.policy_version_id,
                relationship_learning_enabled=record.relationship_learning_enabled,
                semantic_retrieval_enabled=record.semantic_retrieval_enabled,
                provider_extraction_enabled=record.provider_extraction_enabled,
                local_relation_model_enabled=record.local_relation_model_enabled,
                visibility_rules_json=canonical_json(record.visibility_rules),
                change_reason=record.change_reason,
                created_at=record.created_at,
            )
        )
        head = await self._session.get(StoredPolicyHead, 1)
        if head is None:
            self._session.add(
                StoredPolicyHead(singleton_id=1, policy_version_id=record.policy_version_id)
            )
        else:
            head.policy_version_id = record.policy_version_id
        await self._commit()

    async def active_policy_version(self) -> RelationshipMemoryPolicyVersionRecord | None:
        """Return the currently effective immutable relationship-memory policy."""
        statement = select(StoredPolicyVersion).join(
            StoredPolicyHead,
            StoredPolicyHead.policy_version_id == StoredPolicyVersion.policy_version_id,
        )
        stored = await self._session.scalar(statement)
        return None if stored is None else policy_record(stored)

    async def advance_cursor(self, cursor: ArchiveCursor) -> None:
        """Advance one archive cursor without permitting regression."""
        stored = await self._session.get(StoredArchiveCursor, cursor.source_name)
        incoming_key = (as_utc(cursor.archive_created_at), cursor.discord_message_id)
        if stored is not None:
            current_key = (stored.archive_created_at, stored.discord_message_id)
            if incoming_key <= current_key:
                await self._session.rollback()
                return
            stored.archive_created_at = cursor.archive_created_at
            stored.discord_message_id = cursor.discord_message_id
            stored.policy_version_id = cursor.policy_version_id
            stored.updated_at = cursor.updated_at
        else:
            self._session.add(
                StoredArchiveCursor(
                    source_name=cursor.source_name,
                    archive_created_at=cursor.archive_created_at,
                    discord_message_id=cursor.discord_message_id,
                    policy_version_id=cursor.policy_version_id,
                    updated_at=cursor.updated_at,
                )
            )
        await self._commit()

    async def cursor(self, source_name: str) -> ArchiveCursor | None:
        """Return the committed cursor for a named archive source."""
        stored = await self._session.get(StoredArchiveCursor, source_name)
        if stored is None:
            return None
        return ArchiveCursor(
            stored.source_name,
            stored.archive_created_at,
            stored.discord_message_id,
            stored.policy_version_id,
            stored.updated_at,
        )

    async def record_recall(self, event: RecallEventWrite) -> None:
        """Persist one content-free recall trace idempotently."""
        stored = await self._session.get(StoredRecallEvent, event.recall_event_id)
        values = recall_values(event)
        if stored is not None:
            if stored_recall_values(stored) != values:
                await self._session.rollback()
                raise ValueError("recall event id is already bound to different metadata")
            await self._session.rollback()
            return
        self._session.add(StoredRecallEvent(**values))
        await self._commit()

    async def record_recall_feedback(self, feedback: RecallFeedbackWrite) -> None:
        """Attach one immutable ranking outcome to exactly its selected claims."""
        existing = await self._session.scalar(
            select(StoredRecallFeedback).where(
                StoredRecallFeedback.feedback_id == feedback.feedback_id
            )
        )
        if existing is not None:
            links = tuple(
                sorted(
                    (
                        await self._session.scalars(
                            select(StoredRecallFeedbackClaim.claim_id).where(
                                StoredRecallFeedbackClaim.feedback_id == feedback.feedback_id
                            )
                        )
                    ).all()
                )
            )
            expected = (
                feedback.recall_event_id,
                feedback.outcome,
                tuple(sorted(feedback.selected_claim_ids)),
                as_utc(feedback.created_at),
            )
            actual = (existing.recall_event_id, existing.outcome, links, existing.created_at)
            if actual != expected:
                await self._session.rollback()
                raise ValueError("feedback id is already bound to different attribution")
            await self._session.rollback()
            return
        event = await self._session.get(StoredRecallEvent, feedback.recall_event_id)
        if event is None:
            await self._session.rollback()
            raise ValueError("recall event does not exist")
        selected = tuple(sorted(json.loads(event.selected_claim_ids_json)))
        if tuple(sorted(feedback.selected_claim_ids)) != selected:
            await self._session.rollback()
            raise ValueError("feedback claims do not match the recall selection")
        self._session.add(
            StoredRecallFeedback(
                feedback_id=feedback.feedback_id,
                recall_event_id=feedback.recall_event_id,
                outcome=feedback.outcome,
                created_at=feedback.created_at,
            )
        )
        self._session.add_all(
            [
                StoredRecallFeedbackClaim(feedback_id=feedback.feedback_id, claim_id=claim_id)
                for claim_id in selected
            ]
        )
        await self._commit()

    async def migrate_resolved_legacy_facts(
        self,
        sources: Sequence[ArchiveSourceRecord],
        *,
        policy_version_id: str,
        migrated_at: datetime,
    ) -> int:
        """Copy only legacy facts whose author and source resolve to scoped archive rows."""
        by_message = {source.discord_message_id: source for source in sources}
        facts = (await self._session.scalars(select(UserFact).order_by(UserFact.id))).all()
        migrated = 0
        for fact in facts:
            source = by_message.get(fact.source_message_id)
            claim_id = f"legacy-fact-{fact.id}"
            if source is None or source.author_id != fact.user_id:
                continue
            if await self._session.get(StoredClaim, claim_id) is not None:
                continue
            claim = ClaimWrite(
                claim_id=claim_id,
                subject_user_id=fact.user_id,
                visibility_kind=source.visibility_kind,
                guild_id=source.guild_id,
                channel_id=source.channel_id,
                kind="explicit_fact",
                key=fact.fact_key,
                value=fact.fact_value,
                evidence_class="explicit",
                confidence=1.0,
                state="active",
                predecessor_claim_id=None,
                observed_at=source.archive_created_at,
            )
            evidence = EvidenceWrite(
                source_kind=source.source_kind,
                source_id=source.source_id,
                source_message_id=source.discord_message_id,
                source_timestamp=source.archive_created_at,
                visibility_kind=source.visibility_kind,
                guild_id=source.guild_id,
                channel_id=source.channel_id,
                policy_version_id=policy_version_id,
            )
            await self.add_evidence(claim, evidence)
            await self.activate_claim(claim_id, confirmed_at=migrated_at)
            migrated += 1
        return migrated

    async def delete_user_memory(self, subject_user_id: str) -> None:
        """Delete all derived relationship state for one user, preserving source archives."""
        claim_ids = list(
            (
                await self._session.scalars(
                    select(StoredClaim.claim_id).where(
                        StoredClaim.subject_user_id == subject_user_id
                    )
                )
            ).all()
        )
        recall_ids = list(
            (
                await self._session.scalars(
                    select(StoredRecallEvent.recall_event_id).where(
                        StoredRecallEvent.subject_user_id == subject_user_id
                    )
                )
            ).all()
        )
        feedback_ids = list(
            (
                await self._session.scalars(
                    select(StoredRecallFeedback.feedback_id).where(
                        StoredRecallFeedback.recall_event_id.in_(recall_ids)
                    )
                )
            ).all()
        )
        if feedback_ids:
            await self._session.execute(
                delete(StoredRecallFeedbackClaim).where(
                    StoredRecallFeedbackClaim.feedback_id.in_(feedback_ids)
                )
            )
        if claim_ids:
            await self._session.execute(
                delete(StoredRecallFeedbackClaim).where(
                    StoredRecallFeedbackClaim.claim_id.in_(claim_ids)
                )
            )
            await self._session.execute(
                delete(StoredClaimEvidence).where(StoredClaimEvidence.claim_id.in_(claim_ids))
            )
        if recall_ids:
            await self._session.execute(
                delete(StoredRecallFeedback).where(
                    StoredRecallFeedback.recall_event_id.in_(recall_ids)
                )
            )
            await self._session.execute(
                delete(StoredRecallEvent).where(StoredRecallEvent.recall_event_id.in_(recall_ids))
            )
        await self._session.execute(
            delete(StoredProfileHead).where(StoredProfileHead.subject_user_id == subject_user_id)
        )
        await self._session.execute(
            delete(StoredProfileVersion).where(
                StoredProfileVersion.subject_user_id == subject_user_id
            )
        )
        if claim_ids:
            await self._session.execute(
                delete(StoredClaim).where(StoredClaim.claim_id.in_(claim_ids))
            )
        await self._commit()

    async def _require_claim(self, claim_id: str) -> StoredClaim:
        stored = await self._session.get(StoredClaim, claim_id)
        if stored is None:
            await self._session.rollback()
            raise ValueError("claim does not exist")
        return stored

    async def _commit(self) -> None:
        try:
            await self._session.commit()
        except SQLAlchemyError:
            await self._session.rollback()
            raise
