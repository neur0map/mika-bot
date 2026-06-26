"""Async database engine and session factory built from core.config settings."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from mika.core.config import get_settings
from mika.core.paths import data_dir
from mika.persistence import models as _models  # noqa: F401  (registers ORM models)
from mika.persistence.base import Base


@cache
def engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first use."""
    data_dir()
    return create_async_engine(get_settings().database_url, future=True)


@cache
def session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory bound to the engine."""
    return async_sessionmaker(engine(), expire_on_commit=False)


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    """Yield a database session, closing it on exit."""
    async with session_factory()() as active:
        yield active


async def init_db() -> None:
    """Create all tables (models are registered at import time)."""
    async with engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
