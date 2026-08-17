"""Short-session adapter for custom emoji profiles."""

from __future__ import annotations

from mika.persistence.conversations.expression_models import StoredEmojiProfile
from mika.persistence.conversations.expression_profiles import ExpressionProfileRepository
from mika.persistence.engine import session


class ManagedExpressionProfiles:
    """Expose emoji persistence without sharing ORM sessions across events."""

    async def upsert(
        self,
        guild_id: str,
        emoji_id: str,
        name: str,
        animated: bool,
        available: bool,
        description: str,
        family: str,
        confidence: float,
    ) -> None:
        async with session() as active:
            await ExpressionProfileRepository(active).upsert(
                guild_id,
                emoji_id,
                name,
                animated,
                available,
                description,
                family,
                confidence,
            )

    async def list(self, guild_id: str) -> list[StoredEmojiProfile]:
        async with session() as active:
            return await ExpressionProfileRepository(active).list(guild_id)
