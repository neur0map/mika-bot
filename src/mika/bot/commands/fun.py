"""Fun commands: /8ball, /coinflip, /dice, /choose."""

from __future__ import annotations

import secrets
from typing import Any

from discord import Interaction, app_commands

_EIGHTBALL = (
    "yes",
    "no",
    "maybe",
    "definitely",
    "ask again later",
    "no way",
    "absolutely",
    "i wouldn't count on it",
)
_MAX_SIDES = 1000


def _pick(options: tuple[str, ...] | list[str]) -> str:
    return secrets.choice(list(options))


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the fun commands."""

    @tree.command(name="8ball", description="Ask the magic 8-ball a question.")
    @app_commands.describe(question="your yes/no question")
    async def eightball(interaction: Interaction, question: str) -> None:
        await interaction.response.send_message(f"\U0001f3b1 {_pick(_EIGHTBALL)}")

    @tree.command(name="coinflip", description="Flip a coin.")
    async def coinflip(interaction: Interaction) -> None:
        await interaction.response.send_message(_pick(("heads", "tails")))

    @tree.command(name="dice", description="Roll a die.")
    @app_commands.describe(sides="number of sides (default 6)")
    async def dice(interaction: Interaction, sides: int = 6) -> None:
        sides = max(2, min(sides, _MAX_SIDES))
        await interaction.response.send_message(f"\U0001f3b2 {secrets.randbelow(sides) + 1}")

    @tree.command(name="choose", description="Pick one from a comma-separated list.")
    @app_commands.describe(options="comma-separated options")
    async def choose(interaction: Interaction, options: str) -> None:
        items = [item.strip() for item in options.split(",") if item.strip()]
        if not items:
            await interaction.response.send_message("give me options separated by commas")
            return
        await interaction.response.send_message(_pick(items))
