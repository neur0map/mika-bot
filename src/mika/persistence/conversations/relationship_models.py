"""Normalized ORM tables for evidence-backed relationship memory."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from mika.persistence.base import Base


class _UTCDateTime(TypeDecorator[datetime]):
    """Round-trip aware UTC timestamps on SQLite and server databases."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("relationship-memory timestamps must be timezone-aware")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class StoredClaim(Base):
    """One independently versioned relationship claim."""

    __tablename__ = "relationship_claims"

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_user_id: Mapped[str] = mapped_column(String(32), index=True)
    visibility_kind: Mapped[str] = mapped_column(String(32), index=True)
    guild_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    channel_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(64))
    key: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[str] = mapped_column(Text)
    evidence_class: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String(32), index=True)
    predecessor_claim_id: Mapped[str | None] = mapped_column(
        ForeignKey("relationship_claims.claim_id"), nullable=True
    )
    first_observed_at: Mapped[datetime] = mapped_column(_UTCDateTime())
    last_observed_at: Mapped[datetime] = mapped_column(_UTCDateTime())
    last_confirmed_at: Mapped[datetime | None] = mapped_column(_UTCDateTime(), nullable=True)


class StoredClaimEvidence(Base):
    """A deduplicated observation source supporting one claim."""

    __tablename__ = "relationship_claim_evidence"
    __table_args__ = (UniqueConstraint("claim_id", "source_kind", "source_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_claims.claim_id", ondelete="CASCADE"), index=True
    )
    source_kind: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(128))
    source_message_id: Mapped[str] = mapped_column(String(32), index=True)
    source_timestamp: Mapped[datetime] = mapped_column(_UTCDateTime())
    visibility_kind: Mapped[str] = mapped_column(String(32), index=True)
    guild_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    policy_version_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_memory_policy_versions.policy_version_id")
    )


class StoredProfileVersion(Base):
    """An immutable relationship-profile rendering."""

    __tablename__ = "relationship_profile_versions"

    profile_version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_user_id: Mapped[str] = mapped_column(String(32), index=True)
    index_text: Mapped[str] = mapped_column(Text)
    overview_text: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(String(64))
    generator_version: Mapped[str] = mapped_column(String(64))
    policy_version_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_memory_policy_versions.policy_version_id")
    )
    created_at: Mapped[datetime] = mapped_column(_UTCDateTime())


class StoredProfileClaimLink(Base):
    """Lossless claim membership and ordering for an immutable profile version."""

    __tablename__ = "relationship_profile_claim_links"

    profile_version_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_profile_versions.profile_version_id", ondelete="CASCADE"),
        primary_key=True,
    )
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_claims.claim_id", ondelete="CASCADE"), primary_key=True
    )
    layer: Mapped[str] = mapped_column(String(32))
    position: Mapped[int] = mapped_column(Integer)


class StoredProfileHead(Base):
    """Mutable pointer to one user's active immutable profile version."""

    __tablename__ = "relationship_profile_heads"

    subject_user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    profile_version_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_profile_versions.profile_version_id"), unique=True
    )


class StoredProfileScope(Base):
    """Structural visibility attached to one immutable profile version."""

    __tablename__ = "relationship_profile_scopes"

    profile_version_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_profile_versions.profile_version_id", ondelete="CASCADE"),
        primary_key=True,
    )
    visibility_kind: Mapped[str] = mapped_column(String(32), index=True)
    guild_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class StoredScopedProfileHead(Base):
    """Active immutable profile pointer for one exact conversation scope."""

    __tablename__ = "relationship_scoped_profile_heads"

    subject_user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    visibility_kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    guild_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    channel_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    profile_version_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_profile_versions.profile_version_id"), unique=True
    )


class StoredConsolidationCadence(Base):
    """Last successful consolidation timestamp for one exact scope."""

    __tablename__ = "relationship_consolidation_cadence"

    subject_user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    visibility_kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    guild_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    channel_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(_UTCDateTime())


class StoredPolicyVersion(Base):
    """An immutable effective relationship-memory policy."""

    __tablename__ = "relationship_memory_policy_versions"

    policy_version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    relationship_learning_enabled: Mapped[bool] = mapped_column(Boolean)
    semantic_retrieval_enabled: Mapped[bool] = mapped_column(Boolean)
    provider_extraction_enabled: Mapped[bool] = mapped_column(Boolean)
    local_relation_model_enabled: Mapped[bool] = mapped_column(Boolean)
    visibility_rules_json: Mapped[str] = mapped_column(Text)
    change_reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(_UTCDateTime())


class StoredPolicyHead(Base):
    """Singleton pointer to the active immutable policy version."""

    __tablename__ = "relationship_memory_policy_head"

    singleton_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_version_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_memory_policy_versions.policy_version_id"), unique=True
    )


class StoredArchiveCursor(Base):
    """Last committed compound position for one archive source."""

    __tablename__ = "relationship_archive_cursors"

    source_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    archive_created_at: Mapped[datetime] = mapped_column(_UTCDateTime())
    discord_message_id: Mapped[str] = mapped_column(String(32))
    policy_version_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_memory_policy_versions.policy_version_id")
    )
    updated_at: Mapped[datetime] = mapped_column(_UTCDateTime())


class StoredRecallEvent(Base):
    """Content-free audit trace for one relationship-memory recall."""

    __tablename__ = "relationship_recall_events"

    recall_event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_user_id: Mapped[str] = mapped_column(String(32), index=True)
    visibility_kind: Mapped[str] = mapped_column(String(32))
    guild_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    query_hash: Mapped[str] = mapped_column(String(128))
    relation_label: Mapped[str] = mapped_column(String(32))
    candidate_ids_json: Mapped[str] = mapped_column(Text)
    selected_claim_ids_json: Mapped[str] = mapped_column(Text)
    selected_tiers_json: Mapped[str] = mapped_column(Text)
    rejection_reasons_json: Mapped[str] = mapped_column(Text)
    estimated_token_cost: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column(Float)
    retrieval_version: Mapped[str] = mapped_column(String(64))
    policy_version_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_memory_policy_versions.policy_version_id")
    )
    created_at: Mapped[datetime] = mapped_column(_UTCDateTime())


class StoredRecallFeedback(Base):
    """One distinct ranking outcome attached to a recall event."""

    __tablename__ = "relationship_recall_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feedback_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    recall_event_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_recall_events.recall_event_id", ondelete="CASCADE"), index=True
    )
    outcome: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(_UTCDateTime())


class StoredRecallFeedbackClaim(Base):
    """Attribution from one feedback outcome to one selected claim."""

    __tablename__ = "relationship_recall_feedback_claims"

    feedback_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_recall_feedback.feedback_id", ondelete="CASCADE"),
        primary_key=True,
    )
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_claims.claim_id", ondelete="CASCADE"), primary_key=True
    )
