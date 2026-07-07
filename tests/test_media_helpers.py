"""Media search helpers."""

from __future__ import annotations

from mika.bot.media import normalize_media_query


def test_normalize_media_query_keeps_short_mood_terms() -> None:
    query = "A sarcastic, flirty anime eye-roll reaction GIF please!!! https://x.test/a.gif"
    assert normalize_media_query(query) == "sarcastic flirty anime eye-roll reaction gif"


def test_normalize_media_query_drops_empty_noise() -> None:
    assert normalize_media_query("😂😂😂 https://x.test") == ""
