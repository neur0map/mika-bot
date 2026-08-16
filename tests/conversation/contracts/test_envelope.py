"""Conversation contracts preserve social context without platform objects."""

from __future__ import annotations

from datetime import UTC, datetime

from mika.conversation.contracts.envelope import ConversationEnvelope, ReferencedMessage
from mika.conversation.contracts.media import MediaAsset
from mika.conversation.contracts.trace import StageTrace, TurnTrace


def test_visual_inputs_include_current_and_referenced_media_once() -> None:
    current = MediaAsset(
        kind="image",
        url="https://cdn.example/current.png",
        filename="current.png",
        content_type="image/png",
        source="attachment",
    )
    previous = MediaAsset(
        kind="gif",
        url="https://cdn.example/reaction.gif",
        filename="reaction.gif",
        content_type="image/gif",
        source="embed",
    )
    duplicate = MediaAsset(
        kind="gif",
        url=previous.url,
        filename="duplicate.gif",
        content_type="image/gif",
        source="attachment",
    )
    envelope = ConversationEnvelope(
        message_id="2",
        channel_id="10",
        guild_id="20",
        author_id="30",
        author_name="carlos",
        text="this is literally you",
        mentioned=False,
        created_at=datetime(2026, 8, 16, tzinfo=UTC),
        media=(current, duplicate),
        referenced=ReferencedMessage(
            message_id="1",
            author_id="40",
            author_name="alice",
            text="",
            media=(previous,),
        ),
    )

    assert envelope.visual_inputs == (current, duplicate)


def test_trace_add_returns_new_trace_with_ordered_stage() -> None:
    trace = TurnTrace(
        trace_id="trace-1",
        message_id="2",
        channel_id="10",
        stages=(),
    )
    stage = StageTrace(
        stage="ingress",
        outcome="ok",
        reason=None,
        duration_ms=1.5,
        details={"media_count": 2},
    )

    updated = trace.add(stage)

    assert trace.stages == ()
    assert updated.stages == (stage,)
