"""Public records and ports for relationship-memory orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from mika.conversation.context.retrieval import MemoryRecall
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.relationships.contracts import RelationDecision
from mika.conversation.relationships.extraction import EvidenceProposal
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
    RelationshipMemoryPolicyVersionRecord,
)


@dataclass(frozen=True, slots=True)
class ObservationInput:
    """One source message eligible for relationship evidence extraction."""

    source_kind: str
    source_id: str
    message_id: str
    subject_user_id: str
    text: str
    created_at: datetime
    visibility_kind: str
    guild_id: str | None
    channel_id: str | None

    @classmethod
    def from_envelope(cls, envelope: ConversationEnvelope) -> ObservationInput:
        """Build a live observation after the caller confirms visible execution."""
        visibility = "guild" if envelope.guild_id else "direct_message"
        return cls(
            "discord",
            envelope.message_id,
            envelope.message_id,
            envelope.author_id,
            envelope.text,
            envelope.created_at,
            visibility,
            envelope.guild_id or None,
            envelope.channel_id,
        )

    @classmethod
    def from_archive(cls, source: ArchiveSourceRecord) -> ObservationInput:
        """Build an observation from one validated archive source row."""
        return cls(
            source.source_kind,
            source.source_id,
            source.discord_message_id,
            source.author_id,
            source.text,
            source.archive_created_at,
            source.visibility_kind,
            source.guild_id,
            source.channel_id,
        )


@dataclass(frozen=True, slots=True)
class ObservationResult:
    """Content-free outcome for one relationship observation."""

    outcome: str
    policy_version_id: str | None
    candidate_count: int = 0
    activated_count: int = 0


@dataclass(frozen=True, slots=True)
class PendingObservationResult:
    """Bounded archive processing outcome suitable for scheduler telemetry."""

    processed: int
    remaining_hint: bool
    policy_version_id: str | None
    failed_message_id: str | None = None
    retry_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ConsolidationRun:
    """Content-free publication result for one subject consolidation."""

    profile_changed: bool
    policy_version_id: str | None
    profile_version_id: str | None = None
    candidate_count: int = 0
    rejected: bool = False


class RelationshipRepository(Protocol):
    """Persistence operations required by relationship orchestration."""

    async def active_policy_version(self) -> RelationshipMemoryPolicyVersionRecord | None: ...
    async def add_evidence(self, claim: ClaimWrite, evidence: EvidenceWrite) -> ClaimRecord: ...
    async def activate_claim(self, claim_id: str, *, confirmed_at: datetime) -> ClaimRecord: ...
    async def claims_for_subject(self, subject_user_id: str) -> Sequence[ClaimRecord]: ...
    async def evidence_for_claims(
        self, claim_ids: Sequence[str]
    ) -> Sequence[ClaimEvidenceRecord]: ...
    async def active_profile_for_scope(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> ProfileVersionRecord | None: ...
    async def write_profile_version(self, record: ProfileVersionRecord) -> None: ...
    async def publish_consolidation(
        self,
        record: ProfileVersionRecord | None,
        transitions: Sequence[ClaimTransitionRecord],
    ) -> None: ...
    async def record_recall(self, event: RecallEventWrite) -> None: ...
    async def cursor(self, source_name: str) -> ArchiveCursor | None: ...
    async def advance_cursor(self, cursor: ArchiveCursor) -> None: ...
    async def last_consolidated_at(self, subject_user_id: str) -> datetime | None: ...
    async def record_consolidated_at(
        self, subject_user_id: str, completed_at: datetime
    ) -> None: ...
    async def scoped_last_consolidated_at(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> datetime | None: ...
    async def record_scoped_consolidated_at(
        self,
        subject_user_id: str,
        completed_at: datetime,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> None: ...


class EvidenceExtractor(Protocol):
    """Potentially provider-backed extraction boundary."""

    async def extract(
        self, observation: ObservationInput, relation: RelationDecision
    ) -> Sequence[EvidenceProposal]: ...


class RelationClassifier(Protocol):
    """Relation classification boundary."""

    def classify(self, observation: ObservationInput) -> RelationDecision: ...


class RelationshipRetriever(Protocol):
    """Scoped relationship-retrieval boundary."""

    async def retrieve(self, envelope: ConversationEnvelope) -> MemoryRecall: ...


class PendingObservationSource(Protocol):
    """Read-only source used by the bounded background job."""

    def iter_after(
        self, cursor: ArchiveCursor | None, limit: int
    ) -> Sequence[ArchiveSourceRecord]: ...
