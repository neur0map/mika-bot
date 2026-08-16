"""on_message anti-spam listener, registered alongside the AI message handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from mika.bot.antispam import enforce

if TYPE_CHECKING:
    from mika.bot.client import BotApp


def setup(bot: BotApp) -> None:
    """Register the anti-spam listener."""

    async def guard(message: discord.Message) -> None:
        await enforce(message)

    bot.add_listener(guard, "on_message")
