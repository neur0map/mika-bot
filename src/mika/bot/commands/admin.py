"""Admin utilities: emoji cloning and server-setup templates. Permission-gated."""

from __future__ import annotations

import re
from typing import Any

import discord
from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_EMOJI_RE = re.compile(r"<(a)?:(\w+):(\d+)>")
_PRESETS: dict[str, list[str]] = {
    "community": ["welcome", "rules", "announcements", "general", "off-topic", "media"],
    "gaming": ["general", "looking-for-group", "clips", "game-news", "voice-chat"],
    "support": ["start-here", "open-a-ticket", "faq", "announcements"],
}


async def _gate(interaction: Interaction, permission: str) -> discord.Guild | None:
    guild = interaction.guild
    if guild is None:
        await helpers.deny(interaction, "use this inside a server")
        return None
    if not helpers.has_perms(interaction, permission):
        await helpers.deny(interaction, "you don't have permission for that")
        return None
    return guild


def _emoji_url(source: str) -> str | None:
    match = _EMOJI_RE.search(source)
    if match is None:
        return source if source.startswith("http") else None
    animated, _, emoji_id = match.groups()
    extension = "gif" if animated else "png"
    return f"https://cdn.discordapp.com/emojis/{emoji_id}.{extension}"


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the admin utility commands."""

    @tree.command(name="steal", description="Add an emoji from another server or an image URL.")
    @app_commands.describe(name="name for the new emoji", source="a custom emoji or image URL")
    async def steal(interaction: Interaction, name: str, source: str) -> None:
        guild = await _gate(interaction, "manage_emojis")
        if guild is None:
            return
        url = _emoji_url(source)
        if url is None:
            await helpers.deny(interaction, "give me a custom emoji or an image URL")
            return
        await interaction.response.defer()
        try:
            data = await helpers.fetch_bytes(url)
            emoji = await guild.create_custom_emoji(name=name, image=data)
        except Exception as error:
            logger.warning("steal failed: %s", error)
            await interaction.followup.send("couldn't add that emoji")
            return
        await interaction.followup.send(f"added {emoji}")

    @tree.command(name="cloneemoji", description="Copy a custom emoji into this server.")
    @app_commands.describe(emoji="the custom emoji to copy")
    async def cloneemoji(interaction: Interaction, emoji: str) -> None:
        guild = await _gate(interaction, "manage_emojis")
        if guild is None:
            return
        match = _EMOJI_RE.search(emoji)
        url = _emoji_url(emoji)
        if match is None or url is None:
            await helpers.deny(interaction, "give me a custom emoji")
            return
        await interaction.response.defer()
        try:
            data = await helpers.fetch_bytes(url)
            created = await guild.create_custom_emoji(name=match.group(2), image=data)
        except Exception as error:
            logger.warning("cloneemoji failed: %s", error)
            await interaction.followup.send("couldn't clone that emoji")
            return
        await interaction.followup.send(f"cloned {created}")

    @tree.command(name="emojis", description="List this server's custom emojis.")
    async def emojis(interaction: Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await helpers.deny(interaction, "use this inside a server")
            return
        names = " ".join(str(emoji) for emoji in guild.emojis) or "no custom emojis yet"
        await helpers.send(interaction, helpers.clip(names))

    @tree.command(name="removeemoji", description="Delete a custom emoji by name.")
    @app_commands.describe(name="emoji name")
    async def removeemoji(interaction: Interaction, name: str) -> None:
        guild = await _gate(interaction, "manage_emojis")
        if guild is None:
            return
        match = discord.utils.get(guild.emojis, name=name)
        if match is None:
            await helpers.deny(interaction, "no emoji with that name")
            return
        await match.delete()
        await helpers.send(interaction, f"deleted {name}")

    @tree.command(name="addchannel", description="Create a text channel.")
    @app_commands.describe(name="channel name")
    async def addchannel(interaction: Interaction, name: str) -> None:
        guild = await _gate(interaction, "manage_channels")
        if guild is None:
            return
        channel = await guild.create_text_channel(name)
        await helpers.send(interaction, f"created {channel.mention}")

    @tree.command(name="addcategory", description="Create a category.")
    @app_commands.describe(name="category name")
    async def addcategory(interaction: Interaction, name: str) -> None:
        guild = await _gate(interaction, "manage_channels")
        if guild is None:
            return
        await guild.create_category(name)
        await helpers.send(interaction, f"created category {name}")

    @tree.command(name="template", description="Create a starter set of channels from a preset.")
    @app_commands.describe(preset="community, gaming, or support")
    async def template(interaction: Interaction, preset: str) -> None:
        guild = await _gate(interaction, "manage_channels")
        if guild is None:
            return
        channels = _PRESETS.get(preset.lower())
        if channels is None:
            await helpers.deny(interaction, f"unknown preset; try: {', '.join(_PRESETS)}")
            return
        await interaction.response.defer()
        for channel_name in channels:
            await guild.create_text_channel(channel_name)
        await interaction.followup.send(f"created {len(channels)} channels from `{preset}`")

    @tree.command(name="presets", description="List available server templates.")
    async def presets(interaction: Interaction) -> None:
        lines = [f"**{name}**: {', '.join(channels)}" for name, channels in _PRESETS.items()]
        await helpers.send(interaction, "\n".join(lines))
