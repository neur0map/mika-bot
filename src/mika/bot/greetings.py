"""Member join/leave greetings and autorole, driven by per-guild config."""

from __future__ import annotations

import contextlib

import discord

from mika.persistence.repositories.config import get_setting

DEFAULT_WELCOME = "Welcome {user} to **{server}**!"
DEFAULT_GOODBYE = "{user} just left {server}."


def render(template: str, member: discord.abc.User | discord.Member, guild: discord.Guild) -> str:
    """Fill {user}, {server} and {count} placeholders in a greeting template."""
    return (
        template.replace("{user}", member.mention)
        .replace("{server}", guild.name)
        .replace("{count}", str(guild.member_count or 0))
    )


async def _post(guild: discord.Guild, channel_id: str, text: str) -> None:
    channel = guild.get_channel(int(channel_id))
    sender = getattr(channel, "send", None)
    if sender is None:
        return
    with contextlib.suppress(Exception):
        await sender(text)


async def handle_member_join(member: discord.Member) -> None:
    """Assign the autorole and post the welcome message, if configured."""
    guild = member.guild
    role_id = await get_setting(guild.id, "autorole")
    if role_id and role_id.isdigit():
        role = guild.get_role(int(role_id))
        if role is not None:
            with contextlib.suppress(discord.HTTPException):
                await member.add_roles(role, reason="autorole")
    channel_id = await get_setting(guild.id, "welcome_channel")
    if channel_id and channel_id.isdigit():
        template = await get_setting(guild.id, "welcome_message", DEFAULT_WELCOME)
        await _post(guild, channel_id, render(template or DEFAULT_WELCOME, member, guild))


async def handle_member_remove(member: discord.Member) -> None:
    """Post the goodbye message, if configured."""
    guild = member.guild
    channel_id = await get_setting(guild.id, "goodbye_channel")
    if channel_id and channel_id.isdigit():
        template = await get_setting(guild.id, "goodbye_message", DEFAULT_GOODBYE)
        await _post(guild, channel_id, render(template or DEFAULT_GOODBYE, member, guild))
