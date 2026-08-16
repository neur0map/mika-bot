"""Visible Discord action archive records."""

from __future__ import annotations

from types import SimpleNamespace

from mika.conversation.actions import ActionPlan, ExecutionResult, MediaRequest
from mika.discord.execution.archive import build_visible_records


def test_records_include_only_successfully_rendered_actions() -> None:
    message = SimpleNamespace(
        id=41,
        guild=SimpleNamespace(id=2, name="guild"),
        channel=SimpleNamespace(id=3, name="chat"),
    )
    plan = ActionPlan(
        reply="hello",
        reactions=("🔥", "❌"),
        media=MediaRequest("gif", "party"),
        intent="celebration",
        confidence=0.9,
    )
    result = ExecutionResult("42", ("🔥",), None, ("reaction:HTTPException", "media:not_found"))

    message_record, event_record = build_visible_records(
        message,
        plan,
        result,
        bot_user_id="7",
        persona_name="Mika",
        inbound_media_count=1,
        media_context="image context",
        created_at="2026-08-16T00:00:00+00:00",
    )

    assert message_record is not None
    assert message_record["discord_message_id"] == "42"
    assert message_record["reactions"] == ["🔥"]
    assert message_record["media"] == []
    assert event_record["payload"]["failures"] == ["reaction:HTTPException", "media:not_found"]


def test_silent_execution_has_event_but_no_message_record() -> None:
    message = SimpleNamespace(id=41, guild=None, channel=SimpleNamespace(id=3, name="chat"))

    message_record, event_record = build_visible_records(
        message,
        ActionPlan(silence_reason="model_silence"),
        ExecutionResult(None, (), None, ()),
        bot_user_id="7",
        persona_name="Mika",
        inbound_media_count=0,
        media_context="",
        created_at="2026-08-16T00:00:00+00:00",
    )

    assert message_record is None
    assert event_record["payload"]["silenceReason"] == "model_silence"
