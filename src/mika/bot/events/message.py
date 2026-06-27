"""on_message: route mentions and free-chat channels to the AI brain."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from mika.core.config import get_settings
from mika.core.logging import get_logger

if TYPE_CHECKING:
    from mika.bot.client import BotApp

logger = get_logger(__name__)
_MAX_REPLY = 1990


def _in_scope(message: discord.Message, allowed_guilds: set[str]) -> bool:
    """True only for messages in an allowed server. DMs and other servers are out."""
    if message.guild is None:  # never respond in DMs - server-only
        return False
    return not allowed_guilds or str(message.guild.id) in allowed_guilds


def setup(bot: BotApp) -> None:
    """Register the on_message handler."""
    free_channels = set(get_settings().discord.response_channel_id_list)
    allowed_guilds = set(get_settings().discord.guild_id_list)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot or bot.user is None:
            return
        if not _in_scope(message, allowed_guilds):
            return
        mentioned = bot.user.mentioned_in(message)
        free_chat = str(message.channel.id) in free_channels
        if not mentioned and not free_chat:
            return
        text = message.clean_content.replace(f"@{bot.user.display_name}", "").strip()
        if not text:
            return
        try:
            async with message.channel.typing():
                reply = await bot.llm.reply(
                    channel_id=str(message.channel.id),
                    author_id=str(message.author.id),
                    author_name=message.author.display_name,
                    text=text,
                )
        except Exception as error:
            logger.exception("reply failed: %s", error)
            return
        await message.reply(reply[:_MAX_REPLY] or "...")
