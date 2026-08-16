"""Essential commands: /help and /ping."""

from __future__ import annotations

from typing import Any

from discord import Interaction, app_commands

from mika.core.config import get_settings


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the basic commands."""

    @tree.command(name="help", description="See what I can do.")
    async def help_command(interaction: Interaction) -> None:
        name = get_settings().persona.name
        lines = [
            f"Hi, I'm **{name}**. Mention me to chat, or try:",
            "`/ask` - ask me anything (I can search the web)",
            "`/8ball` `/coinflip` `/dice` `/choose` - fun",
            "`/userinfo` `/serverinfo` `/avatar` - info",
            "`/cat` `/dog` - cute animals",
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @tree.command(name="ping", description="Check my latency.")
    async def ping(interaction: Interaction) -> None:
        latency = round(interaction.client.latency * 1000)
        await interaction.response.send_message(f"pong - {latency}ms", ephemeral=True)
