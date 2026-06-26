"""Info commands: /userinfo, /serverinfo, /avatar."""

from __future__ import annotations

from typing import Any

import discord
from discord import Interaction, app_commands


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the info commands."""

    @tree.command(name="userinfo", description="Show info about a user.")
    @app_commands.describe(user="the user (defaults to you)")
    async def userinfo(interaction: Interaction, user: discord.User | None = None) -> None:
        target = user or interaction.user
        embed = discord.Embed(title=str(target))
        embed.add_field(name="ID", value=str(target.id))
        embed.add_field(
            name="Account created", value=discord.utils.format_dt(target.created_at, "R")
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @tree.command(name="serverinfo", description="Show info about this server.")
    async def serverinfo(interaction: Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("use this inside a server", ephemeral=True)
            return
        embed = discord.Embed(title=guild.name)
        embed.add_field(name="Members", value=str(guild.member_count))
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "R"))
        if guild.icon is not None:
            embed.set_thumbnail(url=guild.icon.url)
        await interaction.response.send_message(embed=embed)

    @tree.command(name="avatar", description="Show a user's avatar.")
    @app_commands.describe(user="the user (defaults to you)")
    async def avatar(interaction: Interaction, user: discord.User | None = None) -> None:
        target = user or interaction.user
        await interaction.response.send_message(target.display_avatar.url)
