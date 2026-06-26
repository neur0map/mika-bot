"""Support tickets: private channels members can open, staff can manage."""

from __future__ import annotations

from typing import Any

import discord
from discord import CategoryChannel, Interaction, Member, Role, TextChannel, app_commands

from mika.bot.commands import helpers
from mika.persistence.repositories.config import get_setting, set_setting

_TICKET_PREFIX = "ticket-"


async def _manage_guild(interaction: Interaction) -> discord.Guild | None:
    guild = interaction.guild
    if guild is None:
        await helpers.deny(interaction, "use this inside a server")
        return None
    if not helpers.has_perms(interaction, "manage_guild"):
        await helpers.deny(interaction, "you need the Manage Server permission")
        return None
    return guild


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the ticket commands."""

    @tree.command(name="open", description="Open a private support ticket.")
    @app_commands.describe(reason="what you need help with")
    async def open_ticket(interaction: Interaction, reason: str = "support request") -> None:
        guild = interaction.guild
        member = interaction.user
        if guild is None or not isinstance(member, Member):
            await helpers.deny(interaction, "use this inside a server")
            return
        await interaction.response.defer(ephemeral=True)
        overwrites: dict[Any, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        staff_id = await get_setting(guild.id, "ticket_staffrole")
        if staff_id and staff_id.isdigit():
            role = guild.get_role(int(staff_id))
            if role is not None:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True
                )
        category = None
        category_id = await get_setting(guild.id, "ticket_category")
        if category_id and category_id.isdigit():
            found = guild.get_channel(int(category_id))
            category = found if isinstance(found, CategoryChannel) else None
        channel = await guild.create_text_channel(
            f"{_TICKET_PREFIX}{member.name}", overwrites=overwrites, category=category
        )
        await channel.send(f"{member.mention} opened a ticket: {helpers.clip(reason, 1500)}")
        await interaction.followup.send(f"opened {channel.mention}", ephemeral=True)

    @tree.command(name="close", description="Close the current ticket channel.")
    async def close_ticket(interaction: Interaction) -> None:
        channel = interaction.channel
        if not isinstance(channel, TextChannel) or not channel.name.startswith(_TICKET_PREFIX):
            await helpers.deny(interaction, "use this inside a ticket channel")
            return
        await helpers.send(interaction, "closing this ticket...")
        await channel.delete(reason="ticket closed")

    @tree.command(name="add", description="Add a member to the current ticket.")
    @app_commands.describe(user="member to add")
    async def add_user(interaction: Interaction, user: Member) -> None:
        channel = interaction.channel
        if not isinstance(channel, TextChannel) or not channel.name.startswith(_TICKET_PREFIX):
            await helpers.deny(interaction, "use this inside a ticket channel")
            return
        await channel.set_permissions(user, view_channel=True, send_messages=True)
        await helpers.send(interaction, f"added {user.display_name}")

    @tree.command(name="setcategory", description="Set the category new tickets are created under.")
    @app_commands.describe(category="the category")
    async def setcategory(interaction: Interaction, category: CategoryChannel) -> None:
        guild = await _manage_guild(interaction)
        if guild is None:
            return
        await set_setting(guild.id, "ticket_category", str(category.id))
        await helpers.send(interaction, f"tickets will open under {category.name}", ephemeral=True)

    @tree.command(name="setstaffrole", description="Set the role that can see all tickets.")
    @app_commands.describe(role="the staff role")
    async def setstaffrole(interaction: Interaction, role: Role) -> None:
        guild = await _manage_guild(interaction)
        if guild is None:
            return
        await set_setting(guild.id, "ticket_staffrole", str(role.id))
        await helpers.send(interaction, f"{role.name} can now see tickets", ephemeral=True)

    @tree.command(name="config", description="Show the ticket setup.")
    async def config(interaction: Interaction) -> None:
        guild = await _manage_guild(interaction)
        if guild is None:
            return
        category = await get_setting(guild.id, "ticket_category")
        staff = await get_setting(guild.id, "ticket_staffrole")
        embed = helpers.embed("Ticket setup")
        embed.add_field(name="Category", value=f"<#{category}>" if category else "none")
        embed.add_field(name="Staff role", value=f"<@&{staff}>" if staff else "none")
        await helpers.send(interaction, embed=embed, ephemeral=True)
