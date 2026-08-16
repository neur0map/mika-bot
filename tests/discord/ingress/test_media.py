"""Discord media normalization preserves visual evidence and removes duplicates."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import discord

from mika.discord.ingress.media import media_from_message


def test_media_from_message_normalizes_attachments_embeds_and_stickers() -> None:
    shared_url = "https://cdn.example/reaction.gif"
    message = cast(
        discord.Message,
        SimpleNamespace(
            attachments=[
                SimpleNamespace(
                    url=shared_url,
                    filename="reaction.gif",
                    content_type="image/gif",
                    width=320,
                    height=240,
                )
            ],
            embeds=[
                SimpleNamespace(
                    video=None,
                    image=SimpleNamespace(url=shared_url, width=320, height=240),
                    thumbnail=None,
                    url="https://example.com/post",
                    type="gifv",
                    title="reaction",
                )
            ],
            stickers=[
                SimpleNamespace(
                    url="https://cdn.example/sticker.png",
                    name="wave",
                )
            ],
        ),
    )

    assets = media_from_message(message)

    assert [(asset.kind, asset.source, asset.url) for asset in assets] == [
        ("gif", "attachment", shared_url),
        ("sticker", "sticker", "https://cdn.example/sticker.png"),
    ]
    assert assets[0].width == 320
    assert assets[0].height == 240


def test_media_from_message_ignores_nonvisual_attachments() -> None:
    message = cast(
        discord.Message,
        SimpleNamespace(
            attachments=[
                SimpleNamespace(
                    url="https://cdn.example/report.pdf",
                    filename="report.pdf",
                    content_type="application/pdf",
                    width=None,
                    height=None,
                )
            ],
            embeds=[],
            stickers=[],
        ),
    )

    assert media_from_message(message) == ()
