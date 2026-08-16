"""Bounded recent-context selection."""

from __future__ import annotations

from typing import Protocol

from mika.conversation.context.contracts import ContextMessage, SelectedContext
from mika.conversation.context.retrieval import MemoryRecall
from mika.conversation.contracts import ConversationEnvelope

_PHRASE_CHARS = 180


class RecentMemory(Protocol):
    """Storage capability required by context selection."""

    async def recent(self, channel_id: str) -> list[tuple[str, str, str]]: ...


class ContextRetriever(Protocol):
    async def retrieve(self, envelope: ConversationEnvelope) -> MemoryRecall: ...


class ContextSelector:
    """Select ordered channel history without provider or Discord coupling."""

    def __init__(
        self,
        memory: RecentMemory,
        *,
        phrase_limit: int = 4,
        retriever: ContextRetriever | None = None,
    ) -> None:
        self._memory = memory
        self._phrase_limit = max(0, phrase_limit)
        self._retriever = retriever

    async def select(self, envelope: ConversationEnvelope) -> SelectedContext:
        """Return bounded history and recent assistant wording to avoid."""
        rows = await self._memory.recent(envelope.channel_id)
        history = tuple(ContextMessage(role, author, content) for role, author, content in rows)
        phrases = tuple(
            item.content.strip()[:_PHRASE_CHARS]
            for item in reversed(history)
            if item.role == "assistant" and item.content.strip()
        )[: self._phrase_limit]
        recall = await self._recall(envelope)
        return SelectedContext(
            history=history,
            memory=recall.text,
            avoid_phrases=phrases,
            fact_count=recall.fact_count,
            match_count=recall.match_count,
            feedback_count=recall.feedback_count,
        )

    async def _recall(self, envelope: ConversationEnvelope) -> MemoryRecall:
        if self._retriever is None:
            return MemoryRecall()
        try:
            return await self._retriever.retrieve(envelope)
        except Exception:
            return MemoryRecall()
