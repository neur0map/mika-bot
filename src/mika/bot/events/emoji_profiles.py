"""Synchronize Discord custom emoji metadata with expression profiles."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from mika.conversation.skills.natural_expression.guild_catalog import GuildEmojiDescriptor

if TYPE_CHECKING:
    from mika.bot.client import BotApp


def descriptors(emojis: Iterable[Any]) -> list[GuildEmojiDescriptor]:
    """Reduce Discord objects to conversation-layer metadata."""
    return [
        GuildEmojiDescriptor(
            str(emoji.id),
            str(emoji.name),
            bool(emoji.animated),
            bool(emoji.available),
            tuple(str(role.id) for role in emoji.roles),
        )
        for emoji in emojis
    ]


def setup(bot: BotApp) -> None:
    """Register live guild emoji refreshes."""

    @bot.event
    async def on_guild_emojis_update(guild: Any, before: Any, after: Any) -> None:
        del before
        await bot.llm.sync_guild_emojis(str(guild.id), descriptors(after))
