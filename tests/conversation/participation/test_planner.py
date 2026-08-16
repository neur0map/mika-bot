"""Deterministic social-participation candidate planning."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mika.conversation.context import ContextMessage, SelectedContext
from mika.conversation.contracts import (
    ConversationEnvelope,
    MediaAsset,
    ReferencedMessage,
)
from mika.conversation.participation import ParticipationPlanner


def message(
    text: str,
    *,
    mentioned: bool = False,
    referenced: ReferencedMessage | None = None,
    media: tuple[MediaAsset, ...] = (),
) -> ConversationEnvelope:
    return ConversationEnvelope(
        message_id="m1",
        channel_id="c1",
        guild_id="g1",
        author_id="u1",
        author_name="alice",
        text=text,
        mentioned=mentioned,
        created_at=datetime(2026, 8, 16, tzinfo=UTC),
        media=media,
        referenced=referenced,
    )


@pytest.mark.parametrize(
    ("envelope", "context", "expected"),
    [
        (message("mika pick one", mentioned=True), SelectedContext(), "reply"),
        (message("anyone know why this fails?"), SelectedContext(), "reply"),
        (message("I'll message you the address"), SelectedContext(), "observe"),
        (message("production is staging with witnesses"), SelectedContext(), "react"),
        (
            message("remember the cursed lasagna?"),
            SelectedContext(history=(ContextMessage("user", "ben", "the cursed lasagna"),)),
            "reply",
        ),
        (message("today was honestly rough"), SelectedContext(), "reply"),
        (message("find the dramatic hamster gif", mentioned=True), SelectedContext(), "media"),
        (message("love that the deploy broke on friday"), SelectedContext(), "react"),
        (message("okay smooth talker, that was cute"), SelectedContext(), "reply"),
        (message("my code is artisanal, every bug handcrafted"), SelectedContext(), "react"),
        (message("he said it works on his machine"), SelectedContext(), "media"),
        (message("the build passed first try somehow"), SelectedContext(), "media"),
        (message("I GOT THE JOB"), SelectedContext(), "react"),
        (
            message(
                "rate the cake",
                media=(MediaAsset("image", "https://cdn.example/cake.webp"),),
            ),
            SelectedContext(),
            "reply",
        ),
        (
            message(
                "this is literally you",
                referenced=ReferencedMessage(
                    "m0",
                    "u2",
                    "ben",
                    "",
                    (MediaAsset("gif", "https://cdn.example/face.gif"),),
                ),
            ),
            SelectedContext(),
            "react",
        ),
        (
            message(
                "wait this actually suits you",
                referenced=ReferencedMessage(
                    "m0",
                    "u2",
                    "ben",
                    "new haircut",
                    (MediaAsset("image", "https://cdn.example/hair.png"),),
                ),
            ),
            SelectedContext(),
            "react",
        ),
        (message("  "), SelectedContext(), "observe"),
    ],
)
def test_planner_selects_socially_appropriate_candidate_mode(
    envelope: ConversationEnvelope,
    context: SelectedContext,
    expected: str,
) -> None:
    decision = ParticipationPlanner().plan(envelope, context)

    assert decision.mode == expected
    assert 0.0 <= decision.confidence <= 1.0
    assert decision.reason


def test_private_logistics_override_a_question_mark() -> None:
    decision = ParticipationPlanner().plan(
        message("did you send me the address?"),
        SelectedContext(),
    )

    assert decision.mode == "observe"
    assert decision.reason == "private_logistics"
