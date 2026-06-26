"""on_ready: log identity and set the bot's presence."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from mika.core.logging import get_logger

if TYPE_CHECKING:
    from mika.bot.client import BotApp

logger = get_logger(__name__)


def setup(bot: BotApp) -> None:
    """Register the on_ready handler."""

    @bot.event
    async def on_ready() -> None:
        logger.info("connected as %s", bot.user)
        await bot.change_presence(activity=discord.Game(name="/help"))
