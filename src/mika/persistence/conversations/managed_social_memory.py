"""Short-session adapter for local social-memory repositories."""

from __future__ import annotations

from mika.persistence.conversations.social_memory import SocialMemoryRepository
from mika.persistence.engine import session
from mika.persistence.models.message import Message


class ManagedSocialMemory:
    """Expose social-memory operations without sharing ORM sessions across turns."""

    async def upsert_fact(
        self,
        user_id: str,
        fact_key: str,
        fact_value: str,
        source_message_id: str,
    ) -> None:
        async with session() as active:
            await SocialMemoryRepository(active).upsert_fact(
                user_id, fact_key, fact_value, source_message_id
            )

    async def facts(self, user_id: str, *, limit: int = 12) -> list[tuple[str, str]]:
        async with session() as active:
            return await SocialMemoryRepository(active).facts(user_id, limit=limit)

    async def add_feedback(
        self,
        message_id: str,
        channel_id: str,
        reactor_id: str,
        emoji: str,
        signal: str,
    ) -> None:
        async with session() as active:
            await SocialMemoryRepository(active).add_feedback(
                message_id, channel_id, reactor_id, emoji, signal
            )

    async def feedback_summary(self, channel_id: str, *, limit: int = 100) -> dict[str, int]:
        async with session() as active:
            return await SocialMemoryRepository(active).feedback_summary(channel_id, limit=limit)

    async def candidates(
        self,
        channel_id: str,
        author_id: str,
        *,
        limit: int = 80,
    ) -> list[Message]:
        async with session() as active:
            return await SocialMemoryRepository(active).candidates(
                channel_id,
                author_id,
                limit=limit,
            )
