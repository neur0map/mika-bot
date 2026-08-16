"""Task-scoped tool eligibility planning."""

from __future__ import annotations

from datetime import UTC, datetime

from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.participation import ParticipationDecision
from mika.conversation.tools import ToolPlanner


def envelope(text: str) -> ConversationEnvelope:
    return ConversationEnvelope(
        message_id="m1",
        channel_id="c1",
        guild_id="g1",
        author_id="u1",
        author_name="alice",
        text=text,
        mentioned=False,
        created_at=datetime(2026, 8, 16, tzinfo=UTC),
    )


def test_current_facts_expose_only_web_search() -> None:
    plan = ToolPlanner().plan(
        envelope("what's the weather in Berlin today?"),
        ParticipationDecision("reply", "room_invitation", 0.9),
    )

    assert plan.names == ("web_search",)


def test_media_candidate_exposes_only_media_search() -> None:
    plan = ToolPlanner().plan(
        envelope("send a dramatic hamster gif"),
        ParticipationDecision("media", "explicit_media_request", 1.0),
    )

    assert plan.names == ("media_search",)


def test_casual_joke_exposes_no_tools() -> None:
    plan = ToolPlanner().plan(
        envelope("production is staging with witnesses"),
        ParticipationDecision("react", "punchline", 0.8),
    )

    assert plan.names == ()
