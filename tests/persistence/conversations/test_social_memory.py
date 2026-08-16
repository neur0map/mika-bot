"""Durable local facts, candidates, and feedback."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mika.persistence.base import Base
from mika.persistence.conversations.social_memory import SocialMemoryRepository


async def _repository() -> tuple[SocialMemoryRepository, object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return SocialMemoryRepository(factory()), engine


async def test_fact_upsert_replaces_same_users_key_without_cross_user_leak() -> None:
    repository, engine = await _repository()
    try:
        await repository.upsert_fact("u1", "favorite_game", "Hades", "m1")
        await repository.upsert_fact("u1", "favorite_game", "Hades II", "m2")
        await repository.upsert_fact("u2", "favorite_game", "Celeste", "m3")

        assert await repository.facts("u1") == [("favorite_game", "Hades II")]
        assert await repository.facts("u2") == [("favorite_game", "Celeste")]
    finally:
        await repository.close()
        await engine.dispose()  # type: ignore[attr-defined]


async def test_feedback_is_deduplicated_and_summarized() -> None:
    repository, engine = await _repository()
    try:
        await repository.add_feedback("mika-1", "c1", "u1", "🔥", "positive")
        await repository.add_feedback("mika-1", "c1", "u1", "🔥", "positive")
        await repository.add_feedback("mika-2", "c1", "u2", "👎", "negative")

        assert await repository.feedback_summary("c1") == {"negative": 1, "positive": 1}
    finally:
        await repository.close()
        await engine.dispose()  # type: ignore[attr-defined]


async def test_candidates_are_bounded_to_same_channel_or_user() -> None:
    repository, engine = await _repository()
    try:
        await repository.add_message("c1", "u2", "Ben", "user", "shared launch joke")
        await repository.add_message("c2", "u1", "Ada", "user", "my launch story")
        await repository.add_message("c2", "u9", "Nope", "user", "must not leak")

        rows = await repository.candidates("c1", "u1", limit=2)

        assert {row.content for row in rows} == {"shared launch joke", "my launch story"}
    finally:
        await repository.close()
        await engine.dispose()  # type: ignore[attr-defined]
