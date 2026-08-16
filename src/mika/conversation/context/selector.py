"""Bounded recent-context selection."""

from __future__ import annotations

from typing import Protocol

from mika.conversation.context.contracts import ContextMessage, SelectedContext
from mika.conversation.contracts import ConversationEnvelope

_PHRASE_CHARS = 180


class RecentMemory(Protocol):
    """Storage capability required by context selection."""

    async def recent(self, channel_id: str) -> list[tuple[str, str, str]]: ...


class ContextSelector:
    """Select ordered channel history without provider or Discord coupling."""

    def __init__(self, memory: RecentMemory, *, phrase_limit: int = 4) -> None:
        self._memory = memory
        self._phrase_limit = max(0, phrase_limit)

    async def select(self, envelope: ConversationEnvelope) -> SelectedContext:
        """Return bounded history and recent assistant wording to avoid."""
        rows = await self._memory.recent(envelope.channel_id)
        history = tuple(ContextMessage(role, author, content) for role, author, content in rows)
        phrases = tuple(
            item.content.strip()[:_PHRASE_CHARS]
            for item in reversed(history)
            if item.role == "assistant" and item.content.strip()
        )[: self._phrase_limit]
        return SelectedContext(history=history, avoid_phrases=phrases)
