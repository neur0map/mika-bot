"""Post-turn observation into the canonical conversation store."""

from __future__ import annotations

from typing import Protocol

from mika.conversation.context.contracts import TurnObservation


class WritableMemory(Protocol):
    """Storage capability required by turn observation."""

    async def remember(
        self,
        *,
        channel_id: str,
        author_id: str,
        author_name: str,
        role: str,
        content: str,
    ) -> None: ...


class TurnObserver:
    """Persist user input and only the assistant text that became visible."""

    def __init__(
        self, memory: WritableMemory, *, assistant_id: str = "mika", assistant_name: str = "mika"
    ) -> None:
        self._memory = memory
        self._assistant_id = assistant_id
        self._assistant_name = assistant_name

    async def observe(self, observation: TurnObservation) -> None:
        """Store a completed turn without inventing a message for silence."""
        envelope = observation.envelope
        await self._memory.remember(
            channel_id=envelope.channel_id,
            author_id=envelope.author_id,
            author_name=envelope.author_name,
            role="user",
            content=envelope.text,
        )
        if not observation.reply.strip():
            return
        await self._memory.remember(
            channel_id=envelope.channel_id,
            author_id=self._assistant_id,
            author_name=self._assistant_name,
            role="assistant",
            content=observation.reply,
        )
