"""Bot presence: set the bot's status and activity. Administrator only; global."""

from __future__ import annotations

from typing import Any

import discord
from discord import Interaction, app_commands

from mika.bot.commands import helpers

_STATUS = {
    "online": discord.Status.online,
    "idle": discord.Status.idle,
    "dnd": discord.Status.dnd,
    "invisible": discord.Status.invisible,
}


async def _allowed(interaction: Interaction) -> bool:
    if not helpers.has_perms(interaction, "administrator"):
        await helpers.deny(interaction, "administrator only")
        return False
    return True


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the presence commands."""

    async def _set_activity(interaction: Interaction, activity: discord.BaseActivity) -> bool:
        if not await _allowed(interaction):
            return False
        await interaction.client.change_presence(activity=activity)
        return True

    @tree.command(name="setstatus", description="Set the bot's online status.")
    @app_commands.describe(status="online, idle, dnd, or invisible")
    async def setstatus(interaction: Interaction, status: str) -> None:
        if not await _allowed(interaction):
            return
        chosen = _STATUS.get(status.lower())
        if chosen is None:
            await helpers.deny(interaction, "pick: online, idle, dnd, invisible")
            return
        await interaction.client.change_presence(status=chosen)
        await helpers.send(interaction, f"status set to {status.lower()}", ephemeral=True)

    @tree.command(name="playing", description="Show the bot as Playing something.")
    @app_commands.describe(text="what to show")
    async def playing(interaction: Interaction, text: str) -> None:
        if await _set_activity(interaction, discord.Game(name=text)):
            await helpers.send(interaction, f"now playing {text}", ephemeral=True)

    @tree.command(name="watching", description="Show the bot as Watching something.")
    @app_commands.describe(text="what to show")
    async def watching(interaction: Interaction, text: str) -> None:
        activity = discord.Activity(type=discord.ActivityType.watching, name=text)
        if await _set_activity(interaction, activity):
            await helpers.send(interaction, f"now watching {text}", ephemeral=True)

    @tree.command(name="listening", description="Show the bot as Listening to something.")
    @app_commands.describe(text="what to show")
    async def listening(interaction: Interaction, text: str) -> None:
        activity = discord.Activity(type=discord.ActivityType.listening, name=text)
        if await _set_activity(interaction, activity):
            await helpers.send(interaction, f"now listening to {text}", ephemeral=True)

    @tree.command(name="competing", description="Show the bot as Competing in something.")
    @app_commands.describe(text="what to show")
    async def competing(interaction: Interaction, text: str) -> None:
        activity = discord.Activity(type=discord.ActivityType.competing, name=text)
        if await _set_activity(interaction, activity):
            await helpers.send(interaction, f"now competing in {text}", ephemeral=True)

    @tree.command(name="streaming", description="Show the bot as Streaming with a link.")
    @app_commands.describe(text="stream title", url="twitch or youtube URL")
    async def streaming(interaction: Interaction, text: str, url: str) -> None:
        if await _set_activity(interaction, discord.Streaming(name=text, url=url)):
            await helpers.send(interaction, "streaming set", ephemeral=True)

    @tree.command(name="clearpresence", description="Clear the bot's activity.")
    async def clearpresence(interaction: Interaction) -> None:
        if not await _allowed(interaction):
            return
        await interaction.client.change_presence(activity=None)
        await helpers.send(interaction, "presence cleared", ephemeral=True)
