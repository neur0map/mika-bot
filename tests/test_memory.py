"""Local memory repository: messages persist and come back oldest-first."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mika.persistence.base import Base
from mika.persistence.repositories.messages import MessageRepository


async def test_recent_returns_messages_in_order() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        repo = MessageRepository(session)
        await repo.add(channel_id="c1", author_id="u1", author_name="a", role="user", content="one")
        await repo.add(channel_id="c1", author_id="u1", author_name="a", role="user", content="two")
        await repo.add(
            channel_id="other", author_id="u1", author_name="a", role="user", content="x"
        )
        rows = await repo.recent("c1", 10)
    assert [row.content for row in rows] == ["one", "two"]
