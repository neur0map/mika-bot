"""Per-guild configuration: a small key-value store keyed by guild and key."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mika.persistence.base import Base


class GuildConfig(Base):
    """One configuration value for a guild (welcome message, autorole, and so on)."""

    __tablename__ = "guild_config"

    guild_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
