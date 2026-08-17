"""Privacy-safe relationship-memory operator overview."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mika.persistence.conversations.relationship_records import RelationshipMemoryStatus
from mika.web.routes import overview


@pytest.mark.asyncio
async def test_status_exposes_relationship_health_without_private_content(monkeypatch) -> None:
    snapshot = RelationshipMemoryStatus(
        claim_count=8,
        candidate_count=3,
        active_profile_count=2,
        recall_count=11,
        active_policy_version_id="policy-7",
        learning_enabled=True,
        last_consolidation_at=datetime(2026, 8, 18, tzinfo=UTC),
        archive_source_name="weekly",
        archive_message_id="900",
        archive_updated_at=datetime(2026, 8, 18, 1, tzinfo=UTC),
        operation_health={"recall": {"ok": 11, "failed": 0}},
    )

    async def fake_snapshot() -> RelationshipMemoryStatus:
        return snapshot

    monkeypatch.setattr(overview, "_relationship_snapshot", fake_snapshot)
    result = await overview._status()

    assert result["relationship_memory"] == {
        "claims": 8,
        "candidates": 3,
        "profiles": 2,
        "recalls": 11,
        "policy_version": "policy-7",
        "learning_enabled": True,
        "last_consolidation_at": "2026-08-18T00:00:00+00:00",
        "archive": {
            "source": "weekly",
            "message_id": "900",
            "updated_at": "2026-08-18T01:00:00+00:00",
        },
        "operation_health": {"recall": {"ok": 11, "failed": 0}},
        "degraded": False,
    }
    serialized = repr(result)
    assert "private message" not in serialized
    assert "query_hash" not in serialized


@pytest.mark.asyncio
async def test_status_fails_open_when_relationship_store_is_unavailable(monkeypatch) -> None:
    async def broken_snapshot() -> RelationshipMemoryStatus:
        raise RuntimeError("database unavailable: private message")

    monkeypatch.setattr(overview, "_relationship_snapshot", broken_snapshot)

    result = await overview._status()

    assert result["relationship_memory"] == {"degraded": True}
    assert "private message" not in repr(result)
