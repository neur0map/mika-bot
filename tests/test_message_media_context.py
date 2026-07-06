"""Message media context helpers."""

from __future__ import annotations

from mika.bot.events.message import _media_context


def test_media_context_frames_media_as_social_cue() -> None:
    context = _media_context(
        [
            {
                "kind": "image",
                "source": "embed",
                "name": "sarcastic reaction.gif",
                "embedType": "gifv",
            }
        ]
    )
    assert "treat this socially" in context
    assert "Do not describe" in context
    assert "sarcastic reaction.gif" in context


def test_media_context_empty_without_media() -> None:
    assert _media_context([]) == ""
