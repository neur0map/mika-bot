"""Primitive records exchanged by relationship-memory persistence adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ClaimWrite:
    """Claim fields accepted for a new evidence-backed relationship memory."""

    claim_id: str
    subject_user_id: str
    visibility_kind: str
    guild_id: str | None
    channel_id: str | None
    kind: str
    key: str
    value: str
    evidence_class: str
    confidence: float
    state: str
    predecessor_claim_id: str | None
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class EvidenceWrite:
    """Source reference for one claim observation, without transcript content."""

    source_kind: str
    source_id: str
    source_message_id: str
    source_timestamp: datetime
    visibility_kind: str
    guild_id: str | None
    channel_id: str | None
    policy_version_id: str


@dataclass(frozen=True, slots=True)
class ClaimRecord:
    """Stored claim plus its deduplicated source summary."""

    claim_id: str
    subject_user_id: str
    visibility_kind: str
    guild_id: str | None
    channel_id: str | None
    kind: str
    key: str
    value: str
    evidence_class: str
    confidence: float
    state: str
    predecessor_claim_id: str | None
    source_message_ids: tuple[str, ...]
    observation_count: int
    first_observed_at: datetime
    last_observed_at: datetime
    last_confirmed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ProfileVersionRecord:
    """One immutable rendered relationship-profile version."""

    profile_version_id: str
    subject_user_id: str
    index_text: str
    overview_text: str
    schema_version: str
    generator_version: str
    policy_version_id: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ArchiveCursor:
    """Durable continuation key for one named archive source."""

    source_name: str
    archive_created_at: datetime
    discord_message_id: str
    policy_version_id: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RecallEventWrite:
    """Content-free metadata for one relationship-memory retrieval."""

    recall_event_id: str
    subject_user_id: str
    visibility_kind: str
    guild_id: str | None
    channel_id: str | None
    query_hash: str
    relation_label: str
    candidate_ids: tuple[str, ...]
    selected_claim_ids: tuple[str, ...]
    selected_tiers: Mapping[str, str]
    rejection_reasons: Mapping[str, str]
    estimated_token_cost: int
    latency_ms: float
    retrieval_version: str
    policy_version_id: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RecallFeedbackWrite:
    """Idempotent ranking outcome attributed to one recall and its claims."""

    feedback_id: str
    recall_event_id: str
    outcome: str
    selected_claim_ids: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RelationshipMemoryPolicyVersionRecord:
    """Immutable, content-free effective relationship-memory policy."""

    policy_version_id: str
    relationship_learning_enabled: bool
    semantic_retrieval_enabled: bool
    provider_extraction_enabled: bool
    local_relation_model_enabled: bool
    visibility_rules: Mapping[str, bool]
    change_reason: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ArchiveSourceRecord:
    """Validated source row read transiently from the shared archive."""

    source_kind: str
    source_id: str
    discord_message_id: str
    author_id: str
    author_name: str
    text: str
    archive_created_at: datetime
    visibility_kind: str
    guild_id: str | None
    channel_id: str | None
