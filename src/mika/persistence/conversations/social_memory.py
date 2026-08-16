"""Queries for local user affinity, explicit facts, and reaction feedback."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mika.persistence.conversations.social_models import ReactionFeedback, UserFact
from mika.persistence.models.message import Message


class SocialMemoryRepository:
    """Persist and retrieve bounded social-memory evidence."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def close(self) -> None:
        await self._session.close()

    async def upsert_fact(
        self,
        user_id: str,
        fact_key: str,
        fact_value: str,
        source_message_id: str,
    ) -> None:
        statement = select(UserFact).where(
            UserFact.user_id == user_id,
            UserFact.fact_key == fact_key,
        )
        existing = (await self._session.execute(statement)).scalar_one_or_none()
        if existing is None:
            existing = UserFact(
                user_id=user_id,
                fact_key=fact_key,
                fact_value=fact_value,
                source_message_id=source_message_id,
            )
            self._session.add(existing)
        else:
            existing.fact_value = fact_value
            existing.source_message_id = source_message_id
        await self._session.commit()

    async def facts(self, user_id: str, *, limit: int = 12) -> list[tuple[str, str]]:
        statement = (
            select(UserFact)
            .where(UserFact.user_id == user_id)
            .order_by(UserFact.updated_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(statement)).scalars()
        return [(row.fact_key, row.fact_value) for row in rows]

    async def add_feedback(
        self,
        message_id: str,
        channel_id: str,
        reactor_id: str,
        emoji: str,
        signal: str,
    ) -> None:
        statement = select(ReactionFeedback.id).where(
            ReactionFeedback.message_id == message_id,
            ReactionFeedback.reactor_id == reactor_id,
            ReactionFeedback.emoji == emoji,
        )
        if (await self._session.execute(statement)).scalar_one_or_none() is None:
            self._session.add(
                ReactionFeedback(
                    message_id=message_id,
                    channel_id=channel_id,
                    reactor_id=reactor_id,
                    emoji=emoji,
                    signal=signal,
                )
            )
            await self._session.commit()

    async def feedback_summary(self, channel_id: str, *, limit: int = 100) -> dict[str, int]:
        recent = (
            select(ReactionFeedback.id)
            .where(ReactionFeedback.channel_id == channel_id)
            .order_by(ReactionFeedback.created_at.desc())
            .limit(limit)
            .subquery()
        )
        statement = (
            select(ReactionFeedback.signal, func.count())
            .join(recent, ReactionFeedback.id == recent.c.id)
            .group_by(ReactionFeedback.signal)
        )
        return {signal: count for signal, count in (await self._session.execute(statement)).all()}

    async def candidates(
        self,
        channel_id: str,
        author_id: str,
        *,
        limit: int = 80,
    ) -> list[Message]:
        statement = (
            select(Message)
            .where(or_(Message.channel_id == channel_id, Message.author_id == author_id))
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        return list((await self._session.execute(statement)).scalars())

    async def add_message(
        self,
        channel_id: str,
        author_id: str,
        author_name: str,
        role: str,
        content: str,
    ) -> None:
        self._session.add(
            Message(
                channel_id=channel_id,
                author_id=author_id,
                author_name=author_name,
                role=role,
                content=content,
            )
        )
        await self._session.commit()
