"""Persistence operations for custom emoji semantics."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mika.persistence.conversations.expression_models import StoredEmojiProfile


class ExpressionProfileRepository:
    """Upsert rename-safe emoji profiles and preserve operator corrections."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def close(self) -> None:
        await self._session.close()

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
        """Refresh metadata while respecting a locked semantic correction."""
        statement = select(StoredEmojiProfile).where(
            StoredEmojiProfile.guild_id == guild_id,
            StoredEmojiProfile.emoji_id == emoji_id,
        )
        profile = (await self._session.execute(statement)).scalar_one_or_none()
        if profile is None:
            profile = StoredEmojiProfile(
                guild_id=guild_id,
                emoji_id=emoji_id,
                name=name,
                animated=animated,
                available=available,
                description=description,
                family=family,
                confidence=confidence,
            )
            self._session.add(profile)
        else:
            profile.name = name
            profile.animated = animated
            profile.available = available
            if not profile.locked:
                profile.description = description
                profile.family = family
                profile.confidence = confidence
        await self._session.commit()

    async def correct(self, guild_id: str, emoji_id: str, description: str, family: str) -> None:
        """Apply an authoritative operator correction."""
        statement = select(StoredEmojiProfile).where(
            StoredEmojiProfile.guild_id == guild_id,
            StoredEmojiProfile.emoji_id == emoji_id,
        )
        profile = (await self._session.execute(statement)).scalar_one()
        profile.description = description
        profile.family = family
        profile.confidence = 1.0
        profile.locked = True
        await self._session.commit()

    async def list(self, guild_id: str) -> list[StoredEmojiProfile]:
        """List current and historical profiles for operator inspection."""
        statement = (
            select(StoredEmojiProfile)
            .where(StoredEmojiProfile.guild_id == guild_id)
            .order_by(StoredEmojiProfile.emoji_id)
        )
        return list((await self._session.execute(statement)).scalars())
