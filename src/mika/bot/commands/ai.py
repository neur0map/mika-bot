"""AI command: /ask — chat with the bot through a slash command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from discord import Interaction, app_commands

if TYPE_CHECKING:
    from mika.bot.client import BotApp

_MAX_REPLY = 1990


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the AI command."""

    @tree.command(name="ask", description="Ask me anything - I can search the web.")
    @app_commands.describe(question="your question")
    async def ask(interaction: Interaction, question: str) -> None:
        await interaction.response.defer(thinking=True)
        bot = cast("BotApp", interaction.client)
        reply = await bot.llm.reply(
            channel_id=str(interaction.channel_id),
            author_id=str(interaction.user.id),
            author_name=interaction.user.display_name,
            text=question,
        )
        await interaction.followup.send(reply[:_MAX_REPLY] or "...")
