"""Discord replies preserve the referenced speaker, text, and media."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import discord

from mika.discord.ingress.envelope import envelope_from_message


def test_reply_to_someone_elses_gif_preserves_social_context() -> None:
    referenced = SimpleNamespace(
        id=1,
        author=SimpleNamespace(id=40, display_name="alice", name="alice"),
        content="when the deploy hits friday",
        attachments=[],
        embeds=[
            SimpleNamespace(
                video=None,
                image=SimpleNamespace(url="https://cdn.example/face.gif", width=400, height=300),
                thumbnail=None,
                url="https://example.com/original",
                type="gifv",
                title="face",
            )
        ],
        stickers=[],
    )
    message = cast(
        discord.Message,
        SimpleNamespace(
            id=2,
            channel=SimpleNamespace(id=10),
            guild=SimpleNamespace(id=20),
            author=SimpleNamespace(id=30, display_name="carlos", name="carlos"),
            content="this is literally you",
            created_at=datetime(2026, 8, 16, tzinfo=UTC),
            mentions=[SimpleNamespace(id=999)],
            attachments=[],
            embeds=[],
            stickers=[],
            reference=SimpleNamespace(resolved=referenced),
        ),
    )

    envelope = envelope_from_message(message, bot_user_id=999)

    assert envelope.mentioned is True
    assert envelope.referenced is not None
    assert envelope.referenced.author_name == "alice"
    assert envelope.referenced.text == "when the deploy hits friday"
    assert envelope.visual_inputs[0].kind == "gif"
    assert envelope.visual_inputs[0].url == "https://cdn.example/face.gif"


def test_message_without_reference_has_no_referenced_context() -> None:
    message = cast(
        discord.Message,
        SimpleNamespace(
            id=2,
            channel=SimpleNamespace(id=10),
            guild=SimpleNamespace(id=20),
            author=SimpleNamespace(id=30, display_name="carlos", name="carlos"),
            content="sup",
            created_at=datetime(2026, 8, 16, tzinfo=UTC),
            mentions=[],
            attachments=[],
            embeds=[],
            stickers=[],
            reference=None,
        ),
    )

    envelope = envelope_from_message(message, bot_user_id=999)

    assert envelope.referenced is None
    assert envelope.visual_inputs == ()
