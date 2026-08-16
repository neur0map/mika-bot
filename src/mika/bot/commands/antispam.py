"""Anti-spam and content filters. Configure per server (Manage Server)."""

from __future__ import annotations

from typing import Any

import discord
from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.persistence.repositories.config import all_settings, set_setting

_MAX_RATE = 30
_MAX_WINDOW = 60


async def _guild(interaction: Interaction) -> discord.Guild | None:
    guild = interaction.guild
    if guild is None:
        await helpers.deny(interaction, "use this inside a server")
        return None
    if not helpers.has_perms(interaction, "manage_guild"):
        await helpers.deny(interaction, "you need the Manage Server permission")
        return None
    return guild


async def _toggle(interaction: Interaction, key: str, on: bool, label: str) -> None:
    guild = await _guild(interaction)
    if guild is None:
        return
    await set_setting(guild.id, key, "1" if on else "0")
    await helpers.send(interaction, f"{label} {'on' if on else 'off'}", ephemeral=True)


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the anti-spam configuration commands."""

    @tree.command(name="enable", description="Turn on rate-limit anti-spam.")
    async def enable(interaction: Interaction) -> None:
        await _toggle(interaction, "antispam_enabled", on=True, label="rate-limit anti-spam")

    @tree.command(name="disable", description="Turn off rate-limit anti-spam.")
    async def disable(interaction: Interaction) -> None:
        await _toggle(interaction, "antispam_enabled", on=False, label="rate-limit anti-spam")

    @tree.command(name="rate", description="Set the message rate limit.")
    @app_commands.describe(messages="messages allowed", seconds="per how many seconds")
    async def rate(interaction: Interaction, messages: int, seconds: int) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        messages = max(2, min(messages, _MAX_RATE))
        seconds = max(1, min(seconds, _MAX_WINDOW))
        await set_setting(guild.id, "antispam_rate", str(messages))
        await set_setting(guild.id, "antispam_window", str(seconds))
        await helpers.send(interaction, f"limit: {messages} msgs / {seconds}s", ephemeral=True)

    @tree.command(name="action", description="What to do on spam: delete or timeout.")
    @app_commands.describe(mode="delete or timeout")
    async def action(interaction: Interaction, mode: str) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        if mode.lower() not in {"delete", "timeout"}:
            await helpers.deny(interaction, "pick: delete or timeout")
            return
        await set_setting(guild.id, "antispam_action", mode.lower())
        await helpers.send(interaction, f"action set to {mode.lower()}", ephemeral=True)

    @tree.command(name="invites", description="Block Discord invite links.")
    @app_commands.describe(on="on or off")
    async def invites(interaction: Interaction, on: bool) -> None:
        await _toggle(interaction, "filter_invites", on=on, label="invite filter")

    @tree.command(name="links", description="Block all links.")
    @app_commands.describe(on="on or off")
    async def links(interaction: Interaction, on: bool) -> None:
        await _toggle(interaction, "filter_links", on=on, label="link filter")

    @tree.command(name="caps", description="Block excessive caps.")
    @app_commands.describe(on="on or off")
    async def caps(interaction: Interaction, on: bool) -> None:
        await _toggle(interaction, "filter_caps", on=on, label="caps filter")

    @tree.command(name="mentions", description="Set the max mentions allowed per message.")
    @app_commands.describe(maximum="max mentions (0 disables the check)")
    async def mentions(interaction: Interaction, maximum: int) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        await set_setting(guild.id, "max_mentions", str(max(0, maximum)))
        await helpers.send(interaction, f"max mentions: {max(0, maximum)}", ephemeral=True)

    @tree.command(name="status", description="Show the current anti-spam settings.")
    async def status(interaction: Interaction) -> None:
        guild = await _guild(interaction)
        if guild is None:
            return
        config = await all_settings(guild.id)
        embed = helpers.embed("Anti-spam settings")
        embed.add_field(
            name="Rate limit", value="on" if config.get("antispam_enabled") == "1" else "off"
        )
        embed.add_field(
            name="Invite filter", value="on" if config.get("filter_invites") == "1" else "off"
        )
        embed.add_field(
            name="Link filter", value="on" if config.get("filter_links") == "1" else "off"
        )
        embed.add_field(
            name="Caps filter", value="on" if config.get("filter_caps") == "1" else "off"
        )
        embed.add_field(name="Max mentions", value=config.get("max_mentions", "off"))
        await helpers.send(interaction, embed=embed, ephemeral=True)
