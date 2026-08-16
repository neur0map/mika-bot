"""Message media context helpers."""

from __future__ import annotations

from mika.bot.events.message import _media_context, _media_urls


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
    assert "Treat them socially" in context
    assert "Do not narrate or caption" in context
    assert "sarcastic reaction.gif" in context


def test_media_context_empty_without_media() -> None:
    assert _media_context([]) == ""


def test_media_urls_picks_attachments_by_content_type() -> None:
    urls = _media_urls(
        [
            {"url": "https://cdn.discord/a.png", "contentType": "image/png"},
            {"url": "https://cdn.discord/notes.pdf", "contentType": "application/pdf"},
        ]
    )

    assert urls == ["https://cdn.discord/a.png"]


def test_media_urls_picks_embeds_by_extension() -> None:
    # Tenor/Giphy embeds arrive without a content type.
    urls = _media_urls(
        [
            {"url": "https://media.tenor.com/abc.gif", "source": "embed"},
            {"url": "https://example.com/page", "source": "embed"},
        ]
    )

    assert urls == ["https://media.tenor.com/abc.gif"]


def test_media_urls_ignores_query_string_when_sniffing_extension() -> None:
    urls = _media_urls([{"url": "https://cdn.discord/a.gif?ex=1&is=2", "source": "attachment"}])

    assert urls == ["https://cdn.discord/a.gif?ex=1&is=2"]


def test_media_urls_empty_without_media() -> None:
    assert _media_urls([]) == []
