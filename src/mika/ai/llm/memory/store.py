"""Local recent-window memory backed by the database (always available)."""

from __future__ import annotations

from mika.core.config import get_settings
from mika.persistence.engine import session
from mika.persistence.repositories.messages import MessageRepository


class LocalMemory:
    """The bot's short-term memory: the last N messages per channel."""

    async def remember(
        self,
        *,
        channel_id: str,
        author_id: str,
        author_name: str,
        role: str,
        content: str,
    ) -> None:
        """Persist one message to the channel's history."""
        async with session() as active:
            await MessageRepository(active).add(
                channel_id=channel_id,
                author_id=author_id,
                author_name=author_name,
                role=role,
                content=content,
            )

    async def recent(self, channel_id: str) -> list[tuple[str, str, str]]:
        """Return recent messages as (role, author_name, content), oldest first."""
        window = get_settings().memory.recent_window
        async with session() as active:
            rows = await MessageRepository(active).recent(channel_id, window)
        return [(row.role, row.author_name, row.content) for row in rows]
