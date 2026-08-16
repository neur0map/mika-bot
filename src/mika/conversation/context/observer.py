"""Post-turn observation into the canonical conversation store."""

from __future__ import annotations

from typing import Protocol

from mika.conversation.context.contracts import TurnObservation
from mika.conversation.context.facts import extract_explicit_facts
from mika.core.logging import get_logger

logger = get_logger(__name__)


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


class FactWriter(Protocol):
    async def upsert_fact(
        self,
        user_id: str,
        fact_key: str,
        fact_value: str,
        source_message_id: str,
    ) -> None: ...


class TurnObserver:
    """Persist user input and only the assistant text that became visible."""

    def __init__(
        self,
        memory: WritableMemory,
        *,
        assistant_id: str = "mika",
        assistant_name: str = "mika",
        facts: FactWriter | None = None,
    ) -> None:
        self._memory = memory
        self._assistant_id = assistant_id
        self._assistant_name = assistant_name
        self._facts = facts

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
        if self._facts is not None:
            for key, value in extract_explicit_facts(envelope.text):
                try:
                    await self._facts.upsert_fact(
                        envelope.author_id,
                        key,
                        value,
                        envelope.message_id,
                    )
                except Exception as error:
                    logger.debug("explicit fact persistence failed: %s", error)
        if not observation.reply.strip():
            return
        await self._memory.remember(
            channel_id=envelope.channel_id,
            author_id=self._assistant_id,
            author_name=self._assistant_name,
            role="assistant",
            content=observation.reply,
        )
