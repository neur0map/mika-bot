"""Capture and normalize learning signals from chat feedback."""

from __future__ import annotations

_POSITIVE = {"👍", "❤️", "🔥", "✅", "💯"}
_LAUGH = {"😂", "🤣", "😭", "💀"}
_CONFUSED = {"🤔", "👀", "😬", "❓", "?"}
_NEGATIVE = {"👎", "❌"}


def reaction_signal(emoji: str) -> str:
    """Map one reaction emoji to a coarse learning signal."""
    normalized = emoji.strip()
    if normalized in _POSITIVE:
        return "positive"
    if normalized in _LAUGH:
        return "laugh"
    if normalized in _CONFUSED:
        return "confused"
    if normalized in _NEGATIVE:
        return "negative"
    return "other"
