"""on_reaction_add: capture feedback signals for shared training logs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord

from mika.ai.learning.feedback import reaction_signal
from mika.core.config import get_settings
from mika.core.logging import get_logger
from mika.persistence.shared_archive import archive_event

if TYPE_CHECKING:
    from mika.bot.client import BotApp

logger = get_logger(__name__)


def _iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def setup(bot: BotApp) -> None:
    """Register the reaction feedback handler."""
    allowed_guilds = set(get_settings().discord.guild_id_list)

    @bot.event
    async def on_reaction_add(
        reaction: discord.Reaction, user: discord.User | discord.Member
    ) -> None:
        if user.bot:
            return
        try:
            message = reaction.message
            if message.guild is None:
                return
            if allowed_guilds and str(message.guild.id) not in allowed_guilds:
                return
            emoji = str(reaction.emoji)
            await archive_event(
                {
                    "event_type": "reaction_add",
                    "created_at": _iso(),
                    "guild_id": str(message.guild.id),
                    "guild_name": message.guild.name,
                    "channel_id": str(message.channel.id),
                    "channel_name": getattr(message.channel, "name", None),
                    "discord_message_id": str(message.id),
                    "author": user.display_name,
                    "author_id": str(user.id),
                    "emoji": emoji,
                    "payload": {
                        "source": "mikav2-python",
                        "feedbackSignal": reaction_signal(emoji),
                        "messageAuthorId": str(message.author.id) if message.author else None,
                        "messageAuthorName": message.author.display_name
                        if message.author
                        else None,
                        "isMikav2Message": message.author.id == bot.user.id
                        if bot.user and message.author
                        else False,
                        "reactionCount": reaction.count,
                    },
                }
            )
        except Exception as error:
            logger.warning("reaction archive failed: %s", error)
