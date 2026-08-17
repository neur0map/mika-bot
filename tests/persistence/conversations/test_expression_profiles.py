"""Durable custom emoji profiles and operator corrections."""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mika.persistence.base import Base
from mika.persistence.conversations.expression_profiles import ExpressionProfileRepository


async def _repository() -> tuple[ExpressionProfileRepository, object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return ExpressionProfileRepository(factory()), engine


async def test_upsert_uses_guild_and_snowflake_not_mutable_name() -> None:
    repository, engine = await _repository()
    try:
        await repository.upsert("g", "123", "old", False, True, "a face", "awkwardness", 0.4)
        await repository.upsert("g", "123", "renamed", False, True, "new guess", "warmth", 0.5)

        profiles = await repository.list("g")
        assert len(profiles) == 1
        assert profiles[0].name == "renamed"
        assert profiles[0].description == "new guess"
    finally:
        await repository.close()
        await engine.dispose()  # type: ignore[attr-defined]


async def test_operator_correction_stays_locked_during_sync() -> None:
    repository, engine = await _repository()
    try:
        await repository.upsert("g", "123", "face", False, True, "guess", "warmth", 0.3)
        await repository.correct("g", "123", "disbelief", "skepticism")
        await repository.upsert("g", "123", "face2", False, True, "new guess", "support", 0.8)

        profile = (await repository.list("g"))[0]
        assert profile.description == "disbelief"
        assert profile.family == "skepticism"
        assert profile.locked
        assert profile.name == "face2"
    finally:
        await repository.close()
        await engine.dispose()  # type: ignore[attr-defined]
