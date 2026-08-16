"""on_member_join / on_member_remove: greetings and autorole."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from mika.bot.greetings import handle_member_join, handle_member_remove

if TYPE_CHECKING:
    from mika.bot.client import BotApp


def setup(bot: BotApp) -> None:
    """Register the member join/leave handlers."""

    @bot.event
    async def on_member_join(member: discord.Member) -> None:
        await handle_member_join(member)

    @bot.event
    async def on_member_remove(member: discord.Member) -> None:
        await handle_member_remove(member)
