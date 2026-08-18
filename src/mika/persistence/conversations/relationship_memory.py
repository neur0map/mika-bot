"""Transactional persistence operations for relationship memory."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from mika.persistence.conversations.relationship_integrity import (
    normalize_discord_message_id,
    validate_claim_evidence_scope,
)
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
    StoredConsolidationCadence,
    StoredPolicyHead,
    StoredPolicyVersion,
    StoredProfileClaimLink,
    StoredProfileHead,
    StoredProfileScope,
    StoredProfileVersion,
    StoredRecallEvent,
    StoredRecallFeedback,
    StoredRecallFeedbackClaim,
    StoredScopedProfileHead,
    StoredRelationshipOperation,
)
from mika.persistence.conversations.relationship_publication import (
    publish_consolidation as publish_consolidation_transaction,
)
from mika.persistence.conversations.relationship_records import (
    ArchiveCursor,
    ArchiveSourceRecord,
    ClaimEvidenceRecord,
    ClaimRecord,
    ClaimTransitionRecord,
    ClaimWrite,
    EvidenceWrite,
    ProfileVersionRecord,
    RecallEventWrite,
    RecallFeedbackWrite,
    RelationshipMemoryPolicyVersionRecord,
    RelationshipMemoryStatus,
    RelationshipOperationWrite,
)
from mika.persistence.conversations.relationship_transitions import (
    activate_stored_claim,
    transition_replacement,
    validate_new_predecessor,
)
from mika.persistence.conversations.social_models import UserFact
from mika.persistence.models.guild_config import GuildConfig

_CONSOLIDATION_READ_PAGE_SIZE = 500


class RelationshipMemoryRepository:
    """Persist relationship evidence, versions, cursors, and recall attribution."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def close(self) -> None:
        """Close the repository's database session."""
        await self._session.close()

    async def add_evidence(self, claim: ClaimWrite, evidence: EvidenceWrite) -> ClaimRecord:
        """Create a claim if needed and attach one deduplicated source observation."""
        try:
            validate_claim_evidence_scope(claim, evidence)
        except ValueError:
            await self._session.rollback()
            raise
        await self._require_policy_version(evidence.policy_version_id)
        stored = await self._session.get(StoredClaim, claim.claim_id)
        if stored is None:
            await validate_new_predecessor(self._session, claim)
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
        stored = await activate_stored_claim(self._session, stored, confirmed_at=confirmed_at)
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
        await self._require_policy_version(evidence.policy_version_id)
        await transition_replacement(
            self._session, previous, replacement, evidence, superseded_at=superseded_at
        )
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

    async def claims_for_subject(self, subject_user_id: str) -> list[ClaimRecord]:
        """Return complete lifecycle history for one subject during consolidation."""
        rows: list[StoredClaim] = []
        after: tuple[datetime, str] | None = None
        while True:
            filters = [StoredClaim.subject_user_id == subject_user_id]
            if after is not None:
                observed_at, claim_id = after
                filters.append(
                    or_(
                        StoredClaim.first_observed_at > observed_at,
                        and_(
                            StoredClaim.first_observed_at == observed_at,
                            StoredClaim.claim_id > claim_id,
                        ),
                    )
                )
            statement = (
                select(StoredClaim)
                .where(*filters)
                .order_by(StoredClaim.first_observed_at, StoredClaim.claim_id)
                .limit(_CONSOLIDATION_READ_PAGE_SIZE)
            )
            page = list((await self._session.scalars(statement)).all())
            rows.extend(page)
            if len(page) < _CONSOLIDATION_READ_PAGE_SIZE:
                break
            last = page[-1]
            after = (last.first_observed_at, last.claim_id)
        return [await claim_record(self._session, row) for row in rows]

    async def evidence_for_claims(self, claim_ids: Sequence[str]) -> list[ClaimEvidenceRecord]:
        """Return complete primitive evidence rows for the supplied claim identities."""
        if not claim_ids:
            return []
        unique_ids = tuple(dict.fromkeys(claim_ids))
        rows: list[StoredClaimEvidence] = []
        for start in range(0, len(unique_ids), _CONSOLIDATION_READ_PAGE_SIZE):
            page_ids = unique_ids[start : start + _CONSOLIDATION_READ_PAGE_SIZE]
            statement = select(StoredClaimEvidence).where(
                StoredClaimEvidence.claim_id.in_(page_ids)
            )
            rows.extend((await self._session.scalars(statement)).all())
        rows.sort(key=lambda row: (row.source_timestamp, row.source_message_id, row.id))
        return [
            ClaimEvidenceRecord(
                row.claim_id,
                row.source_kind,
                row.source_id,
                row.source_message_id,
                row.source_timestamp,
                row.visibility_kind,
                row.guild_id,
                row.channel_id,
                row.policy_version_id,
            )
            for row in rows
        ]

    async def write_profile_version(self, record: ProfileVersionRecord) -> None:
        """Insert an immutable profile version and atomically move its user's head."""
        await publish_consolidation_transaction(self._session, record, ())

    async def publish_consolidation(
        self,
        record: ProfileVersionRecord | None,
        transitions: Sequence[ClaimTransitionRecord],
    ) -> None:
        """Publish profile and lifecycle changes in one transaction."""
        await publish_consolidation_transaction(self._session, record, transitions)

    async def active_profiles_for_subject(self, subject_user_id: str) -> list[ProfileVersionRecord]:
        """Enumerate every active scoped profile head for one subject."""
        scoped = list(
            (
                await self._session.scalars(
                    select(StoredScopedProfileHead)
                    .where(StoredScopedProfileHead.subject_user_id == subject_user_id)
                    .order_by(
                        StoredScopedProfileHead.visibility_kind,
                        StoredScopedProfileHead.guild_key,
                        StoredScopedProfileHead.channel_key,
                    )
                )
            ).all()
        )
        profiles: list[ProfileVersionRecord] = []
        for scoped_head in scoped:
            profile = await self.active_profile_for_scope(
                subject_user_id,
                visibility_kind=scoped_head.visibility_kind,
                guild_id=scoped_head.guild_key or None,
                channel_id=scoped_head.channel_key or None,
            )
            if profile is not None:
                profiles.append(profile)
        return profiles

    async def _legacy_active_profile(self, subject_user_id: str) -> ProfileVersionRecord | None:
        """Read only the pre-scoped legacy head during compatibility migrations."""
        statement = (
            select(StoredProfileVersion)
            .join(
                StoredProfileHead,
                StoredProfileHead.profile_version_id == StoredProfileVersion.profile_version_id,
            )
            .where(StoredProfileHead.subject_user_id == subject_user_id)
        )
        stored = await self._session.scalar(statement)
        if stored is None:
            return None
        links = list(
            (
                await self._session.scalars(
                    select(StoredProfileClaimLink)
                    .where(StoredProfileClaimLink.profile_version_id == stored.profile_version_id)
                    .order_by(
                        StoredProfileClaimLink.layer,
                        StoredProfileClaimLink.position,
                        StoredProfileClaimLink.claim_id,
                    )
                )
            ).all()
        )
        return profile_record(stored, links)

    async def active_profile_for_scope(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> ProfileVersionRecord | None:
        """Return only the profile published for the exact requested scope."""
        guild_key, channel_key = _scope_key(guild_id, channel_id)
        statement = (
            select(StoredProfileVersion, StoredProfileScope)
            .join(
                StoredScopedProfileHead,
                StoredScopedProfileHead.profile_version_id
                == StoredProfileVersion.profile_version_id,
            )
            .join(
                StoredProfileScope,
                StoredProfileScope.profile_version_id == StoredProfileVersion.profile_version_id,
            )
            .where(
                StoredScopedProfileHead.subject_user_id == subject_user_id,
                StoredScopedProfileHead.visibility_kind == visibility_kind,
                StoredScopedProfileHead.guild_key == guild_key,
                StoredScopedProfileHead.channel_key == channel_key,
            )
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        stored, scope = row
        links = list(
            (
                await self._session.scalars(
                    select(StoredProfileClaimLink)
                    .where(StoredProfileClaimLink.profile_version_id == stored.profile_version_id)
                    .order_by(
                        StoredProfileClaimLink.layer,
                        StoredProfileClaimLink.position,
                        StoredProfileClaimLink.claim_id,
                    )
                )
            ).all()
        )
        return profile_record(stored, links, scope)

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

    async def last_consolidated_at(self, subject_user_id: str) -> datetime | None:
        """Return the independent durable timestamp of the last successful run."""
        stored = await self._session.get(GuildConfig, (0, _consolidation_key(subject_user_id)))
        if stored is not None:
            return as_utc(datetime.fromisoformat(stored.value))
        latest: datetime | None = await self._session.scalar(
            select(func.max(StoredConsolidationCadence.completed_at)).where(
                StoredConsolidationCadence.subject_user_id == subject_user_id
            )
        )
        return latest

    async def record_consolidated_at(self, subject_user_id: str, completed_at: datetime) -> None:
        """Persist successful consolidation even when it publishes no profile."""
        key = _consolidation_key(subject_user_id)
        stored = await self._session.get(GuildConfig, (0, key))
        value = as_utc(completed_at).isoformat()
        if stored is None:
            self._session.add(GuildConfig(guild_id=0, key=key, value=value))
        else:
            stored.value = value
        await self._commit()

    async def scoped_last_consolidated_at(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> datetime | None:
        """Return consolidation cadence for the exact requested scope."""
        guild_key, channel_key = _scope_key(guild_id, channel_id)
        stored = await self._session.get(
            StoredConsolidationCadence,
            (subject_user_id, visibility_kind, guild_key, channel_key),
        )
        return None if stored is None else stored.completed_at

    async def record_scoped_consolidated_at(
        self,
        subject_user_id: str,
        completed_at: datetime,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> None:
        """Persist successful consolidation cadence for one exact scope."""
        guild_key, channel_key = _scope_key(guild_id, channel_id)
        key = (subject_user_id, visibility_kind, guild_key, channel_key)
        stored = await self._session.get(StoredConsolidationCadence, key)
        if stored is None:
            self._session.add(
                StoredConsolidationCadence(
                    subject_user_id=subject_user_id,
                    visibility_kind=visibility_kind,
                    guild_key=guild_key,
                    channel_key=channel_key,
                    completed_at=completed_at,
                )
            )
        else:
            stored.completed_at = completed_at
        await self._commit()

    async def status(self) -> RelationshipMemoryStatus:
        """Return content-free relationship-memory counts and checkpoint health."""
        policy = await self.active_policy_version()
        claim_count = int(
            await self._session.scalar(select(func.count()).select_from(StoredClaim)) or 0
        )
        candidate_count = int(
            await self._session.scalar(
                select(func.count())
                .select_from(StoredClaim)
                .where(StoredClaim.state == "candidate")
            )
            or 0
        )
        profile_count = int(
            await self._session.scalar(select(func.count()).select_from(StoredScopedProfileHead))
            or 0
        )
        recall_count = int(
            await self._session.scalar(select(func.count()).select_from(StoredRecallEvent)) or 0
        )
        last_consolidation = await self._session.scalar(
            select(func.max(StoredProfileVersion.created_at))
        )
        archive = await self._session.scalar(
            select(StoredArchiveCursor).order_by(StoredArchiveCursor.updated_at.desc()).limit(1)
        )
        health_rows = list(
            (
                await self._session.scalars(
                    select(StoredRelationshipOperation)
                    .order_by(StoredRelationshipOperation.created_at.desc())
                    .limit(1000)
                )
            ).all()
        )
        return RelationshipMemoryStatus(
            claim_count,
            candidate_count,
            profile_count,
            recall_count,
            None if policy is None else policy.policy_version_id,
            bool(policy and policy.relationship_learning_enabled),
            last_consolidation,
            None if archive is None else archive.source_name,
            None if archive is None else archive.discord_message_id,
            None if archive is None else archive.updated_at,
            _operation_health(health_rows),
        )

    async def record_operation(self, record: RelationshipOperationWrite) -> None:
        """Persist a content-free runtime operation for health aggregation."""
        self._session.add(
            StoredRelationshipOperation(
                operation=record.operation,
                outcome=record.outcome,
                correlation_hash=record.correlation_hash,
                duration_ms=record.duration_ms,
                candidate_count=record.candidate_count,
                selected_count=record.selected_count,
                rejected_count=record.rejected_count,
                estimated_tokens=record.estimated_tokens,
                fallback_reason=record.fallback_reason,
                profile_changed=record.profile_changed,
                policy_version_id=record.policy_version_id,
                phase_durations_json=canonical_json(record.phase_durations_ms),
                created_at=record.created_at,
            )
        )
        await self._commit()

    async def advance_cursor(self, cursor: ArchiveCursor) -> None:
        """Advance one archive cursor without permitting regression."""
        message_id = normalize_discord_message_id(cursor.discord_message_id)
        await self._require_policy_version(cursor.policy_version_id)
        stored = await self._session.get(StoredArchiveCursor, cursor.source_name)
        incoming_key = (as_utc(cursor.archive_created_at), int(message_id))
        if stored is not None:
            current_key = (stored.archive_created_at, int(stored.discord_message_id))
            if incoming_key <= current_key:
                await self._session.rollback()
                return
            stored.archive_created_at = cursor.archive_created_at
            stored.discord_message_id = message_id
            stored.policy_version_id = cursor.policy_version_id
            stored.updated_at = cursor.updated_at
        else:
            self._session.add(
                StoredArchiveCursor(
                    source_name=cursor.source_name,
                    archive_created_at=cursor.archive_created_at,
                    discord_message_id=message_id,
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
        await self._require_policy_version(event.policy_version_id)
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
            delete(StoredScopedProfileHead).where(
                StoredScopedProfileHead.subject_user_id == subject_user_id
            )
        )
        await self._session.execute(
            delete(StoredConsolidationCadence).where(
                StoredConsolidationCadence.subject_user_id == subject_user_id
            )
        )
        await self._session.execute(
            delete(StoredProfileClaimLink).where(
                StoredProfileClaimLink.profile_version_id.in_(
                    select(StoredProfileVersion.profile_version_id).where(
                        StoredProfileVersion.subject_user_id == subject_user_id
                    )
                )
            )
        )
        await self._session.execute(
            delete(StoredProfileScope).where(
                StoredProfileScope.profile_version_id.in_(
                    select(StoredProfileVersion.profile_version_id).where(
                        StoredProfileVersion.subject_user_id == subject_user_id
                    )
                )
            )
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
        stored = await self._session.scalar(
            select(StoredClaim).where(StoredClaim.claim_id == claim_id).with_for_update()
        )
        if stored is None:
            await self._session.rollback()
            raise ValueError("claim does not exist")
        return stored

    async def _require_policy_version(self, policy_version_id: str) -> None:
        if await self._session.get(StoredPolicyVersion, policy_version_id) is None:
            await self._session.rollback()
            raise ValueError("policy version does not exist")

    async def _commit(self) -> None:
        try:
            await self._session.commit()
        except SQLAlchemyError:
            await self._session.rollback()
            raise


def _consolidation_key(subject_user_id: str) -> str:
    digest = hashlib.sha256(subject_user_id.encode()).hexdigest()[:24]
    return f"relationship_consolidated:{digest}"


def _scope_key(guild_id: str | None, channel_id: str | None) -> tuple[str, str]:
    return (guild_id or "", channel_id or "")


def _operation_health(
    rows: Sequence[StoredRelationshipOperation],
) -> dict[str, dict[str, int | float]]:
    grouped: dict[str, list[StoredRelationshipOperation]] = {}
    for row in rows:
        grouped.setdefault(row.operation, []).append(row)
    result: dict[str, dict[str, int | float]] = {}
    for operation, records in grouped.items():
        durations = sorted(item.duration_ms for item in records)
        percentile = durations[max(0, math.ceil(len(durations) * 0.95) - 1)]
        result[operation] = {
            "total": len(records),
            "failed": sum(item.outcome == "failed" for item in records),
            "fallback": sum(bool(item.fallback_reason) for item in records),
            "retry": sum(item.outcome == "retry" for item in records),
            "dead_letter": sum(item.outcome == "dead_letter" for item in records),
            "unhealthy": sum(
                item.outcome in {"failed", "retry", "dead_letter", "rejected"} for item in records
            ),
            "p95_ms": round(percentile, 3),
        }
        phase_names = sorted(
            {name for item in records for name in json.loads(item.phase_durations_json or "{}")}
        )
        for phase_name in phase_names:
            values = sorted(
                float(json.loads(item.phase_durations_json or "{}").get(phase_name, 0.0))
                for item in records
                if phase_name in json.loads(item.phase_durations_json or "{}")
            )
            index = max(0, math.ceil(len(values) * 0.95) - 1)
            result[operation][f"p95_{phase_name}_ms"] = round(values[index], 3)
    return result
