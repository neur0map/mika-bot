"""ORM models. Importing this package registers every model on the metadata."""

from __future__ import annotations

from mika.persistence.models.guild_config import GuildConfig
from mika.persistence.models.message import Message

__all__ = ["GuildConfig", "Message"]
