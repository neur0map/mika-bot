"""Data access for per-guild configuration values."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from mika.persistence.engine import init_db, session
from mika.persistence.models.guild_config import GuildConfig

_STATE: dict[str, bool] = {}


async def _ensure() -> None:
    if not _STATE.get("ready"):
        await init_db()
        _STATE["ready"] = True


class ConfigRepository:
    """Read and write per-guild settings."""

    def __init__(self, db: AsyncSession) -> None:
        self._session = db

    async def get(self, guild_id: int, key: str) -> str | None:
        row = await self._session.get(GuildConfig, (guild_id, key))
        return row.value if row is not None else None

    async def set(self, guild_id: int, key: str, value: str) -> None:
        row = await self._session.get(GuildConfig, (guild_id, key))
        if row is None:
            self._session.add(GuildConfig(guild_id=guild_id, key=key, value=value))
        else:
            row.value = value

    async def remove(self, guild_id: int, key: str) -> None:
        await self._session.execute(
            delete(GuildConfig).where(GuildConfig.guild_id == guild_id, GuildConfig.key == key)
        )


async def get_setting(guild_id: int, key: str, default: str | None = None) -> str | None:
    """Return a guild setting, or default when it isn't set."""
    await _ensure()
    async with session() as db:
        value = await ConfigRepository(db).get(guild_id, key)
    return value if value is not None else default


async def set_setting(guild_id: int, key: str, value: str) -> None:
    """Store a guild setting."""
    await _ensure()
    async with session() as db:
        await ConfigRepository(db).set(guild_id, key, value)
        await db.commit()


async def delete_setting(guild_id: int, key: str) -> None:
    """Remove a guild setting."""
    await _ensure()
    async with session() as db:
        await ConfigRepository(db).remove(guild_id, key)
        await db.commit()
