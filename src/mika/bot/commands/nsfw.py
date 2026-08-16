"""Age-gated image fetchers backed by the keyless waifu.im API."""

from __future__ import annotations

from typing import Any

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_ENDPOINT = "https://api.waifu.im/search"
_GATE = "use this in an age-restricted channel"
_FALLBACK = "couldn't fetch one right now"

_COMMANDS: list[tuple[str, str, str]] = [
    ("nsfwwaifu", "waifu", "A spicy waifu."),
    ("hentai", "hentai", "A hentai image."),
    ("milf", "milf", "A milf image."),
    ("oral", "oral", "An oral image."),
    ("ero", "ero", "An ero image."),
    ("ass", "ass", "An ass image."),
]


async def _fetch_url(tag: str) -> str:
    data = await helpers.fetch_json(_ENDPOINT, included_tags=tag, is_nsfw="true")
    return str(data["images"][0]["url"])


def _register(tree: app_commands.CommandTree[Any], name: str, tag: str, desc: str) -> None:
    @tree.command(name=name, description=desc)
    async def _cmd(interaction: Interaction) -> None:
        if not helpers.is_nsfw(interaction):
            await helpers.deny(interaction, _GATE)
            return
        await interaction.response.defer()
        try:
            url = await _fetch_url(tag)
        except Exception as error:
            logger.warning("%s fetch failed: %s", name, error)
            await interaction.followup.send(_FALLBACK)
            return
        picture = helpers.embed()
        picture.set_image(url=url)
        await interaction.followup.send(embed=picture)


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the age-gated image commands."""
    for name, tag, desc in _COMMANDS:
        _register(tree, name, tag, desc)
