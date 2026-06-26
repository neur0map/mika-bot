"""Welcome and goodbye messages plus autorole. Configure per server (Manage Server)."""

from __future__ import annotations

from typing import Any

import discord
from discord import Interaction, Role, TextChannel, app_commands

from mika.bot.commands import helpers
from mika.bot.greetings import DEFAULT_WELCOME, render
from mika.persistence.repositories.config import delete_setting, get_setting, set_setting


async def _guild(interaction: Interaction) -> discord.Guild | None:
    guild = interaction.guild
    if guild is None:
        await helpers.deny(interaction, "use this inside a server")
        return None
    if not helpers.has_perms(interaction, "manage_guild"):
        await helpers.deny(interaction, "you need the Manage Server permission")
        return None
    return guild


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the welcome/goodbye/autorole commands."""

    @tree.command(name="welcomechannel", description="Set the channel for welcome messages.")
    @app_commands.describe(channel="where to post welcomes")
    async def welcomechannel(interaction: Interaction, channel: TextChannel) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        await set_setting(guild.id, "welcome_channel", str(channel.id))
        await helpers.send(interaction, f"welcomes will post in {channel.mention}", ephemeral=True)

    @tree.command(
        name="welcomemessage", description="Set the welcome text. Use {user}, {server}, {count}."
    )
    @app_commands.describe(message="the welcome message")
    async def welcomemessage(interaction: Interaction, message: str) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        await set_setting(guild.id, "welcome_message", message)
        await helpers.send(interaction, "welcome message saved", ephemeral=True)

    @tree.command(name="welcometest", description="Preview the welcome message.")
    async def welcometest(interaction: Interaction) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        template = await get_setting(guild.id, "welcome_message", DEFAULT_WELCOME)
        await helpers.send(
            interaction, render(template or DEFAULT_WELCOME, interaction.user, guild)
        )

    @tree.command(name="welcomeoff", description="Stop posting welcome messages.")
    async def welcomeoff(interaction: Interaction) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        await delete_setting(guild.id, "welcome_channel")
        await helpers.send(interaction, "welcomes turned off", ephemeral=True)

    @tree.command(name="goodbyechannel", description="Set the channel for goodbye messages.")
    @app_commands.describe(channel="where to post goodbyes")
    async def goodbyechannel(interaction: Interaction, channel: TextChannel) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        await set_setting(guild.id, "goodbye_channel", str(channel.id))
        await helpers.send(interaction, f"goodbyes will post in {channel.mention}", ephemeral=True)

    @tree.command(name="goodbyemessage", description="Set the goodbye text. Use {user}, {server}.")
    @app_commands.describe(message="the goodbye message")
    async def goodbyemessage(interaction: Interaction, message: str) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        await set_setting(guild.id, "goodbye_message", message)
        await helpers.send(interaction, "goodbye message saved", ephemeral=True)

    @tree.command(name="goodbyeoff", description="Stop posting goodbye messages.")
    async def goodbyeoff(interaction: Interaction) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        await delete_setting(guild.id, "goodbye_channel")
        await helpers.send(interaction, "goodbyes turned off", ephemeral=True)

    @tree.command(name="autorole", description="Give new members this role automatically.")
    @app_commands.describe(role="role to grant on join")
    async def autorole(interaction: Interaction, role: Role) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        await set_setting(guild.id, "autorole", str(role.id))
        await helpers.send(interaction, f"new members will get {role.name}", ephemeral=True)

    @tree.command(name="autoroleoff", description="Stop auto-assigning a role on join.")
    async def autoroleoff(interaction: Interaction) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        await delete_setting(guild.id, "autorole")
        await helpers.send(interaction, "autorole turned off", ephemeral=True)

    @tree.command(name="greetings", description="Show the current welcome/goodbye/autorole setup.")
    async def greetings(interaction: Interaction) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        welcome = await get_setting(guild.id, "welcome_channel")
        goodbye = await get_setting(guild.id, "goodbye_channel")
        role = await get_setting(guild.id, "autorole")
        embed = helpers.embed("Greeting setup")
        embed.add_field(name="Welcome channel", value=f"<#{welcome}>" if welcome else "off")
        embed.add_field(name="Goodbye channel", value=f"<#{goodbye}>" if goodbye else "off")
        embed.add_field(name="Autorole", value=f"<@&{role}>" if role else "off")
        await helpers.send(interaction, embed=embed, ephemeral=True)
