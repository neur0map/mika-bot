"""Structured chat turn result used by Discord event handlers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MediaChoice:
    """Optional expressive media choice for a reply."""

    kind: str = "none"
    query: str | None = None


@dataclass(frozen=True, slots=True)
class MikaTurn:
    """One bot decision: text, optional reaction, optional media."""

    reply: str
    reactions: tuple[str, ...] = ()
    media: MediaChoice = MediaChoice()
    intent: str = "chat"
    confidence: float = 0.5
    schema_version: str = "mika_turn.v2"
    raw: str = ""
