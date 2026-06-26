"""Self-learning: the bot reflects on recent chats to improve over time (admin)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from discord import Interaction, app_commands

from mika.ai.learning.reflection import last_reflection, run_reflection
from mika.bot.commands import helpers
from mika.persistence.repositories.config import set_setting

if TYPE_CHECKING:
    from mika.bot.client import BotApp

_GLOBAL = 0


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the self-learning commands."""

    @tree.command(name="reflect", description="Run a self-reflection pass now (admin).")
    async def reflect(interaction: Interaction) -> None:
        if not helpers.has_perms(interaction, "manage_guild"):
            await helpers.deny(interaction, "you need the Manage Server permission")
            return
        await interaction.response.defer(ephemeral=True)
        bot = cast("BotApp", interaction.client)
        lessons = await run_reflection(bot.llm)
        await interaction.followup.send(helpers.clip(f"**Reflection**\n{lessons}"), ephemeral=True)

    @tree.command(name="recent", description="Show the bot's latest self-reflection.")
    async def recent(interaction: Interaction) -> None:
        text, when = await last_reflection()
        if not text:
            await helpers.send(
                interaction, "no reflection yet - try /learning reflect", ephemeral=True
            )
            return
        await helpers.send(
            interaction, helpers.clip(f"**Last reflection** ({when})\n{text}"), ephemeral=True
        )

    @tree.command(name="auto", description="Turn the weekly reflection loop on or off (admin).")
    @app_commands.describe(on="on or off")
    async def auto(interaction: Interaction, on: bool) -> None:
        if not helpers.has_perms(interaction, "manage_guild"):
            await helpers.deny(interaction, "you need the Manage Server permission")
            return
        await set_setting(_GLOBAL, "reflection_auto", "1" if on else "0")
        await helpers.send(
            interaction, f"weekly reflection turned {'on' if on else 'off'}", ephemeral=True
        )
