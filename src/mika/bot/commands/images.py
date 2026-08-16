"""Animal image commands: /cat and /dog (keyless public APIs)."""

from __future__ import annotations

from typing import Any

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the animal-image commands."""

    @tree.command(name="cat", description="A random cat.")
    async def cat(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://api.thecatapi.com/v1/images/search")
            url = str(data[0]["url"])
        except Exception as error:
            logger.warning("cat fetch failed: %s", error)
            await interaction.followup.send("couldn't fetch a cat right now")
            return
        await interaction.followup.send(url)

    @tree.command(name="dog", description="A random dog.")
    async def dog(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://dog.ceo/api/breeds/image/random")
            url = str(data["message"])
        except Exception as error:
            logger.warning("dog fetch failed: %s", error)
            await interaction.followup.send("couldn't fetch a dog right now")
            return
        await interaction.followup.send(url)
