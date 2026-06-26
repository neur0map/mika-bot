"""Data access for conversation messages (the local recent-memory window)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mika.persistence.models.message import Message


class MessageRepository:
    """Read and write chat messages for one bot instance."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        channel_id: str,
        author_id: str,
        author_name: str,
        role: str,
        content: str,
    ) -> Message:
        """Persist one message and return it."""
        message = Message(
            channel_id=channel_id,
            author_id=author_id,
            author_name=author_name,
            role=role,
            content=content,
        )
        self._session.add(message)
        await self._session.commit()
        return message

    async def recent(self, channel_id: str, limit: int) -> list[Message]:
        """Return the most recent messages for a channel, oldest first."""
        stmt = (
            select(Message)
            .where(Message.channel_id == channel_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(reversed(rows))
