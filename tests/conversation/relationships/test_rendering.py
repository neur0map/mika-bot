"""Whole-tier relationship-memory budget allocation."""

from datetime import UTC, datetime

from mika.conversation.context.contracts import MemoryCandidate
from mika.conversation.relationships.contracts import RelationDecision
from mika.conversation.relationships.rendering import TieredMemoryRenderer, estimate_tokens


def _candidate(candidate_id: str, index_text: str) -> MemoryCandidate:
    return MemoryCandidate(
        candidate_id,
        "u1",
        "channel",
        "g1",
        "c1",
        "claim",
        index_text,
        None,
        None,
        "repeated_behavior",
        0.8,
        datetime(2026, 8, 17, tzinfo=UTC),
    )


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

    rendered = TieredMemoryRenderer(token_budget=7).render(
        (candidate,), RelationDecision("memory_probe", 1.0, "probe")
    )

    assert rendered.selected_tiers == {"memory": "overview"}
    assert rendered.text.endswith("overview fits this budget")
    assert rendered.rejection_reasons["memory"] == "token_budget:evidence->overview"


def test_multi_item_cost_includes_all_rendered_framing() -> None:
    rendered = TieredMemoryRenderer(token_budget=8).render(
        (_candidate("first", "first index"), _candidate("second", "second index")),
        RelationDecision("follow_up", 1.0, "follow-up"),
    )

    actual_cost = estimate_tokens(rendered.text)
    assert rendered.selected_ids == ("first", "second")
    assert actual_cost <= 8
    assert rendered.estimated_token_cost == actual_cost
