"""Shared real-SQLite fixtures for relationship-memory persistence tests."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from mika.persistence.base import Base
from mika.persistence.conversations.relationship_memory import RelationshipMemoryRepository
from mika.persistence.conversations.relationship_records import (
    ClaimWrite,
    EvidenceWrite,
    ProfileVersionRecord,
    RecallEventWrite,
    RelationshipMemoryPolicyVersionRecord,
)

NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)


async def repository(path: Path) -> tuple[RelationshipMemoryRepository, AsyncEngine]:
    """Create a repository backed by an on-disk temporary SQLite database."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return RelationshipMemoryRepository(factory()), engine


def policy(version_id: str = "policy-1") -> RelationshipMemoryPolicyVersionRecord:
    """Build a deterministic policy version for persistence tests."""
    return RelationshipMemoryPolicyVersionRecord(
        policy_version_id=version_id,
        relationship_learning_enabled=True,
        semantic_retrieval_enabled=False,
        provider_extraction_enabled=False,
        local_relation_model_enabled=False,
        visibility_rules={"dm_to_public": False},
        change_reason="initial rollout",
        created_at=NOW,
    )


def claim(
    claim_id: str,
    *,
    user_id: str = "user-1",
    value: str = "Hades",
    evidence_class: str = "explicit",
    state: str = "candidate",
    visibility_kind: str = "guild",
    guild_id: str | None = "guild-1",
    channel_id: str | None = None,
    predecessor_claim_id: str | None = None,
) -> ClaimWrite:
    """Build a deterministic claim write for persistence tests."""
    return ClaimWrite(
        claim_id=claim_id,
        subject_user_id=user_id,
        visibility_kind=visibility_kind,
        guild_id=guild_id,
        channel_id=channel_id,
        kind="interest",
        key="favorite_game",
        value=value,
        evidence_class=evidence_class,
        confidence=0.95,
        state=state,
        predecessor_claim_id=predecessor_claim_id,
        observed_at=NOW,
    )


def evidence(
    source_id: str,
    *,
    source_message_id: str | None = None,
    visibility_kind: str = "guild",
    guild_id: str | None = "guild-1",
    channel_id: str | None = "channel-1",
) -> EvidenceWrite:
    """Build a deterministic evidence write for persistence tests."""
    return EvidenceWrite(
        source_kind="discord_archive",
        source_id=source_id,
        source_message_id=source_message_id or source_id,
        source_timestamp=NOW,
        visibility_kind=visibility_kind,
        guild_id=guild_id,
        channel_id=channel_id,
        policy_version_id="policy-1",
    )


def profile(version_id: str, overview: str) -> ProfileVersionRecord:
    """Build a deterministic immutable profile version for persistence tests."""
    return ProfileVersionRecord(
        profile_version_id=version_id,
        subject_user_id="user-1",
        index_text="likes action roguelikes",
        overview_text=overview,
        schema_version="relationship-profile-v1",
        generator_version="deterministic-v1",
        policy_version_id="policy-1",
        created_at=NOW,
    )


def recall_event(event_id: str = "recall-1") -> RecallEventWrite:
    """Build deterministic content-free recall metadata for persistence tests."""
    return RecallEventWrite(
        recall_event_id=event_id,
        subject_user_id="user-1",
        visibility_kind="guild",
        guild_id="guild-1",
        channel_id="channel-1",
        query_hash="sha256:query",
        relation_label="memory_probe",
        candidate_ids=("claim-1", "claim-2"),
        selected_claim_ids=("claim-1",),
        selected_tiers={"claim-1": "overview"},
        rejection_reasons={"claim-2": "below_threshold"},
        estimated_token_cost=21,
        latency_ms=3.5,
        retrieval_version="retrieval-v1",
        policy_version_id="policy-1",
        created_at=NOW,
    )


def create_archive(path: Path) -> None:
    """Create a shared-archive fixture containing valid and degraded rows."""
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE messages (
                id TEXT PRIMARY KEY,
                author TEXT,
                author_id TEXT,
                content TEXT,
                created_at TEXT,
                guild_id TEXT,
                channel_id TEXT,
                discord_message_id TEXT,
                metadata_json TEXT
            )
            """
        )
        rows = (
            (
                "row-2",
                "Ada",
                "user-1",
                "second",
                "2026-08-17T12:00:00+00:00",
                "g",
                "c",
                "101",
                "{}",
            ),
            (
                "row-1",
                "Ada",
                "user-1",
                "first",
                "2026-08-17T12:00:00Z",
                "g",
                "c",
                "100",
                '{"visibility_kind":"channel"}',
            ),
            (
                "row-3",
                "Ada",
                "user-1",
                "third",
                "2026-08-17T12:01:00+00:00",
                None,
                "dm",
                "102",
                "{}",
            ),
            ("bad-time", "Ada", "user-1", "skip", "2026-08-17 12:02:00", "g", "c", "103", "{}"),
            (
                "bad-id",
                "Ada",
                "user-1",
                "skip",
                "2026-08-17T12:03:00+00:00",
                "g",
                "c",
                "not-a-snowflake",
                "{}",
            ),
        )
        connection.executemany("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?)", rows)
