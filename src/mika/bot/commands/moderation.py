"""Moderation: bans, kicks, timeouts, roles, channel control. Permission-gated."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import discord
from discord import Interaction, Member, Role, TextChannel, app_commands

from mika.bot.commands import helpers

_MAX_PURGE = 100
_MAX_SLOWMODE = 21600
_DAY_SECONDS = 86400


async def _gate(interaction: Interaction, permission: str) -> discord.Guild | None:
    guild = interaction.guild
    if guild is None:
        await helpers.deny(interaction, "use this inside a server")
        return None
    if not helpers.has_perms(interaction, permission):
        await helpers.deny(interaction, "you don't have permission for that")
        return None
    return guild


async def _text_channel(interaction: Interaction) -> TextChannel | None:
    channel = interaction.channel
    if not isinstance(channel, TextChannel):
        await helpers.deny(interaction, "use this in a text channel")
        return None
    return channel


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the moderation commands."""

    @tree.command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(user="member to kick", reason="reason")
    async def kick(interaction: Interaction, user: Member, reason: str = "no reason given") -> None:
        if await _gate(interaction, "kick_members") is None:
            return
        await user.kick(reason=reason)
        await helpers.send(interaction, f"kicked {user.display_name}")

    @tree.command(name="ban", description="Ban a member from the server.")
    @app_commands.describe(user="member to ban", reason="reason")
    async def ban(interaction: Interaction, user: Member, reason: str = "no reason given") -> None:
        if await _gate(interaction, "ban_members") is None:
            return
        await user.ban(reason=reason)
        await helpers.send(interaction, f"banned {user.display_name}")

    @tree.command(name="banid", description="Ban a user by ID, even if they aren't here.")
    @app_commands.describe(user_id="the user's ID", reason="reason")
    async def banid(
        interaction: Interaction, user_id: str, reason: str = "no reason given"
    ) -> None:
        guild = await _gate(interaction, "ban_members")
        if guild is None:
            return
        try:
            target = discord.Object(id=int(user_id))
        except ValueError:
            await helpers.deny(interaction, "that isn't a valid ID")
            return
        await guild.ban(target, reason=reason)
        await helpers.send(interaction, f"banned `{user_id}`")

    @tree.command(name="unban", description="Unban a user by ID.")
    @app_commands.describe(user_id="the user's ID")
    async def unban(interaction: Interaction, user_id: str) -> None:
        guild = await _gate(interaction, "ban_members")
        if guild is None:
            return
        try:
            target = discord.Object(id=int(user_id))
        except ValueError:
            await helpers.deny(interaction, "that isn't a valid ID")
            return
        await guild.unban(target)
        await helpers.send(interaction, f"unbanned `{user_id}`")

    @tree.command(name="softban", description="Ban then immediately unban to clear messages.")
    @app_commands.describe(user="member", reason="reason")
    async def softban(interaction: Interaction, user: Member, reason: str = "cleanup") -> None:
        guild = await _gate(interaction, "ban_members")
        if guild is None:
            return
        await user.ban(reason=reason, delete_message_seconds=_DAY_SECONDS)
        await guild.unban(discord.Object(id=user.id))
        await helpers.send(interaction, f"softbanned {user.display_name}")

    @tree.command(name="timeout", description="Time a member out for some minutes.")
    @app_commands.describe(user="member", minutes="minutes (max 28 days)", reason="reason")
    async def timeout(
        interaction: Interaction, user: Member, minutes: int, reason: str = "no reason given"
    ) -> None:
        if await _gate(interaction, "moderate_members") is None:
            return
        minutes = max(1, min(minutes, 40320))
        await user.timeout(timedelta(minutes=minutes), reason=reason)
        await helpers.send(interaction, f"timed out {user.display_name} for {minutes}m")

    @tree.command(name="untimeout", description="Remove a member's timeout.")
    @app_commands.describe(user="member")
    async def untimeout(interaction: Interaction, user: Member) -> None:
        if await _gate(interaction, "moderate_members") is None:
            return
        await user.timeout(None)
        await helpers.send(interaction, f"cleared timeout on {user.display_name}")

    @tree.command(name="purge", description="Bulk-delete recent messages in this channel.")
    @app_commands.describe(amount="how many (max 100)")
    async def purge(interaction: Interaction, amount: int) -> None:
        if await _gate(interaction, "manage_messages") is None:
            return
        channel = await _text_channel(interaction)
        if channel is None:
            return
        amount = max(1, min(amount, _MAX_PURGE))
        deleted = await channel.purge(limit=amount)
        await helpers.send(interaction, f"deleted {len(deleted)} messages", ephemeral=True)

    @tree.command(name="slowmode", description="Set this channel's slowmode in seconds.")
    @app_commands.describe(seconds="delay in seconds (0 to disable)")
    async def slowmode(interaction: Interaction, seconds: int) -> None:
        if await _gate(interaction, "manage_channels") is None:
            return
        channel = await _text_channel(interaction)
        if channel is None:
            return
        seconds = max(0, min(seconds, _MAX_SLOWMODE))
        await channel.edit(slowmode_delay=seconds)
        await helpers.send(interaction, f"slowmode set to {seconds}s")

    @tree.command(name="setnick", description="Change a member's nickname.")
    @app_commands.describe(user="member", nickname="new nickname")
    async def setnick(interaction: Interaction, user: Member, nickname: str) -> None:
        if await _gate(interaction, "manage_nicknames") is None:
            return
        await user.edit(nick=nickname)
        await helpers.send(interaction, f"renamed {user.display_name}")

    @tree.command(name="addrole", description="Give a member a role.")
    @app_commands.describe(user="member", role="role to add")
    async def addrole(interaction: Interaction, user: Member, role: Role) -> None:
        if await _gate(interaction, "manage_roles") is None:
            return
        await user.add_roles(role)
        await helpers.send(interaction, f"gave {role.name} to {user.display_name}")

    @tree.command(name="removerole", description="Take a role from a member.")
    @app_commands.describe(user="member", role="role to remove")
    async def removerole(interaction: Interaction, user: Member, role: Role) -> None:
        if await _gate(interaction, "manage_roles") is None:
            return
        await user.remove_roles(role)
        await helpers.send(interaction, f"removed {role.name} from {user.display_name}")

    @tree.command(name="createrole", description="Create a new role.")
    @app_commands.describe(name="role name")
    async def createrole(interaction: Interaction, name: str) -> None:
        guild = await _gate(interaction, "manage_roles")
        if guild is None:
            return
        role = await guild.create_role(name=name)
        await helpers.send(interaction, f"created role {role.name}")

    @tree.command(name="deleterole", description="Delete a role.")
    @app_commands.describe(role="role to delete")
    async def deleterole(interaction: Interaction, role: Role) -> None:
        if await _gate(interaction, "manage_roles") is None:
            return
        await role.delete()
        await helpers.send(interaction, "role deleted")

    @tree.command(name="lock", description="Stop everyone from sending messages here.")
    async def lock(interaction: Interaction) -> None:
        guild = await _gate(interaction, "manage_channels")
        if guild is None:
            return
        channel = await _text_channel(interaction)
        if channel is None:
            return
        await channel.set_permissions(guild.default_role, send_messages=False)
        await helpers.send(interaction, "channel locked")

    @tree.command(name="unlock", description="Allow everyone to send messages here again.")
    async def unlock(interaction: Interaction) -> None:
        guild = await _gate(interaction, "manage_channels")
        if guild is None:
            return
        channel = await _text_channel(interaction)
        if channel is None:
            return
        await channel.set_permissions(guild.default_role, send_messages=None)
        await helpers.send(interaction, "channel unlocked")

    @tree.command(name="settopic", description="Set this channel's topic.")
    @app_commands.describe(topic="the new topic")
    async def settopic(interaction: Interaction, topic: str) -> None:
        if await _gate(interaction, "manage_channels") is None:
            return
        channel = await _text_channel(interaction)
        if channel is None:
            return
        await channel.edit(topic=topic)
        await helpers.send(interaction, "topic updated")

    @tree.command(name="say", description="Send a message as the bot.")
    @app_commands.describe(message="what to say")
    async def say(interaction: Interaction, message: str) -> None:
        if await _gate(interaction, "manage_messages") is None:
            return
        channel = await _text_channel(interaction)
        if channel is None:
            return
        await channel.send(helpers.clip(message))
        await helpers.send(interaction, "sent", ephemeral=True)

    @tree.command(name="announce", description="Post an embedded announcement.")
    @app_commands.describe(message="announcement text")
    async def announce(interaction: Interaction, message: str) -> None:
        if await _gate(interaction, "manage_messages") is None:
            return
        channel = await _text_channel(interaction)
        if channel is None:
            return
        await channel.send(embed=helpers.embed("Announcement", helpers.clip(message)))
        await helpers.send(interaction, "announced", ephemeral=True)
