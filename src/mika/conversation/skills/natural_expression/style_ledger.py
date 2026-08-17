"""Bounded fingerprints of recent assistant expression."""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass

from mika.conversation.skills.natural_expression.contracts import StyleSnapshot

_EMOJI = re.compile(r"<a?:[^:>]+:\d+>|[\U0001F300-\U0001FAFF\u2600-\u27BF]")
_OPENING = re.compile(r"[\w']+", re.UNICODE)
_PROTECTED = re.compile(r"`[^`]*`|\"[^\"]*\"|https?://\S+")


@dataclass(frozen=True, slots=True)
class _Entry:
    """One assistant reply reduced to style-only signals."""

    emoji: tuple[str, ...]
    opening: str
    dash: bool


class StyleLedger:
    """Keep only a short window of non-content fingerprints per channel."""

    def __init__(self, window: int = 4) -> None:
        self._entries: dict[str, deque[_Entry]] = defaultdict(lambda: deque(maxlen=window))

    def observe(self, channel_id: str, reply: str, reactions: tuple[str, ...]) -> None:
        """Record style from output that was actually rendered."""
        visible = _PROTECTED.sub("", reply)
        words = _OPENING.findall(visible)
        found = tuple(_EMOJI.findall(visible)) + reactions
        self._entries[channel_id].append(
            _Entry(
                found,
                words[0].lower() if words else "",
                "—" in visible or "\u2013" in visible,
            )
        )

    def snapshot(self, channel_id: str) -> StyleSnapshot:
        """Return recent fingerprints without reply content."""
        entries = tuple(self._entries.get(channel_id, ()))
        emoji = tuple(item for entry in entries for item in entry.emoji)
        openings = tuple(entry.opening for entry in entries if entry.opening)
        dash_ages = tuple(
            len(entries) - index - 1 for index, entry in enumerate(entries) if entry.dash
        )
        return StyleSnapshot(emoji, (), openings, dash_ages)
