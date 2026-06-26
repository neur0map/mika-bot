"""Giveaways: reaction draws ended by the host, plus an instant raffle from a list."""

from __future__ import annotations

import contextlib
import secrets
from typing import Any

import discord
from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_PARTY = "\U0001f389"


async def _manage(interaction: Interaction) -> discord.Guild | None:
    guild = interaction.guild
    if guild is None:
        await helpers.deny(interaction, "use this inside a server")
        return None
    if not helpers.has_perms(interaction, "manage_guild"):
        await helpers.deny(interaction, "you need the Manage Server permission")
        return None
    return guild


async def _draw(interaction: Interaction, message_id: str, winners: int) -> None:
    if not message_id.isdigit():
        await helpers.deny(interaction, "give me the giveaway message ID")
        return
    fetch = getattr(interaction.channel, "fetch_message", None)
    if fetch is None:
        await helpers.deny(interaction, "use this in the giveaway's channel")
        return
    try:
        message = await fetch(int(message_id))
        reaction = discord.utils.get(message.reactions, emoji=_PARTY)
        entrants = [user async for user in reaction.users() if not user.bot] if reaction else []
        if not entrants:
            await helpers.send(interaction, "nobody entered that giveaway")
            return
        picks = secrets.SystemRandom().sample(entrants, min(max(1, winners), len(entrants)))
        await helpers.send(interaction, f"{_PARTY} winners: " + ", ".join(u.mention for u in picks))
    except Exception as error:
        logger.warning("draw failed: %s", error)
        await helpers.send(interaction, "couldn't read that giveaway")


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the giveaway commands."""

    @tree.command(name="start", description="Start a reaction giveaway.")
    @app_commands.describe(prize="what's being given away", winners="how many winners")
    async def start(interaction: Interaction, prize: str, winners: int = 1) -> None:
        if await _manage(interaction) is None:
            return
        embed = helpers.embed(
            f"{_PARTY} Giveaway {_PARTY}", f"**{prize}**\n\nReact with {_PARTY} to enter!"
        )
        embed.set_footer(text=f"{max(1, winners)} winner(s) - the host ends it with /giveaway end")
        await interaction.response.send_message(embed=embed)
        with contextlib.suppress(Exception):
            message = await interaction.original_response()
            await message.add_reaction(_PARTY)

    @tree.command(name="end", description="End a giveaway and draw winners.")
    @app_commands.describe(message_id="the giveaway message ID", winners="how many winners")
    async def end(interaction: Interaction, message_id: str, winners: int = 1) -> None:
        if await _manage(interaction) is None:
            return
        await _draw(interaction, message_id, winners)

    @tree.command(name="reroll", description="Draw new winners for a finished giveaway.")
    @app_commands.describe(message_id="the giveaway message ID", winners="how many winners")
    async def reroll(interaction: Interaction, message_id: str, winners: int = 1) -> None:
        if await _manage(interaction) is None:
            return
        await _draw(interaction, message_id, winners)

    @tree.command(name="pick", description="Instantly pick winners from a comma-separated list.")
    @app_commands.describe(prize="the prize", entries="comma-separated names", winners="how many")
    async def pick(interaction: Interaction, prize: str, entries: str, winners: int = 1) -> None:
        names = [name.strip() for name in entries.split(",") if name.strip()]
        if not names:
            await helpers.deny(interaction, "give me comma-separated entries")
            return
        chosen = secrets.SystemRandom().sample(names, min(max(1, winners), len(names)))
        await helpers.send(interaction, f"{_PARTY} **{prize}** -> {', '.join(chosen)}")
