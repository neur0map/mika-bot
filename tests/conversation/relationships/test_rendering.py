"""Whole-tier relationship-memory budget allocation."""

from datetime import UTC, datetime

from mika.conversation.context.contracts import MemoryCandidate
from mika.conversation.relationships.contracts import RelationDecision
from mika.conversation.relationships.rendering import TieredMemoryRenderer


def test_memory_probe_uses_overview_when_evidence_does_not_fit() -> None:
    candidate = MemoryCandidate(
        "memory",
        "u1",
        "channel",
        "g1",
        "c1",
        "claim",
        "compact index",
        "overview fits this budget",
        "evidence has far too many words to fit inside this small remaining budget",
        "repeated_behavior",
        0.8,
        datetime(2026, 8, 17, tzinfo=UTC),
    )

    rendered = TieredMemoryRenderer(token_budget=6).render(
        (candidate,), RelationDecision("memory_probe", 1.0, "probe")
    )

    assert rendered.selected_tiers == {"memory": "overview"}
    assert rendered.text.endswith("overview fits this budget")
    assert rendered.rejection_reasons["memory"] == "token_budget:evidence->overview"
