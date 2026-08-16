"""GIF, sticker and clip search via the Klipy API (free key from partner.klipy.com)."""

from __future__ import annotations

import secrets
from typing import Any

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.config import get_settings
from mika.core.logging import get_logger

logger = get_logger(__name__)

_MEDIA_SUFFIXES = (".gif", ".gifv", ".mp4", ".webp", ".webm")
_NO_KEY = (
    "GIF search needs a free Klipy API key. Get one at partner.klipy.com and add it "
    "to your bot's .env file (see the setup docs)."
)


def _first_media_url(obj: Any) -> str | None:
    if isinstance(obj, str):
        low = obj.lower()
        return obj if obj.startswith("http") and low.endswith(_MEDIA_SUFFIXES) else None
    if isinstance(obj, dict):
        for value in obj.values():
            found = _first_media_url(value)
            if found:
                return found
    if isinstance(obj, list):
        for value in obj:
            found = _first_media_url(value)
            if found:
                return found
    return None


async def _search(interaction: Interaction, kind: str, query: str) -> None:
    key = get_settings().media.klipy_api_key
    if not key:
        await helpers.deny(interaction, _NO_KEY)
        return
    await interaction.response.defer()
    try:
        data = await helpers.fetch_json(
            f"https://api.klipy.com/api/v1/{key}/{kind}/search", q=query, per_page=24
        )
        results = data.get("data", {}).get("data") or data.get("data") or []
        results = results if isinstance(results, list) else []
        if not results:
            await interaction.followup.send("no results for that")
            return
        url = _first_media_url(secrets.choice(results)) or _first_media_url(results)
        await interaction.followup.send(url or "no playable result found")
    except Exception as error:
        logger.warning("klipy %s failed: %s", kind, error)
        await interaction.followup.send("couldn't reach the GIF service")


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the GIF/sticker/clip commands."""

    @tree.command(name="gif", description="Search for a GIF.")
    @app_commands.describe(query="what to search for")
    async def gif(interaction: Interaction, query: str) -> None:
        await _search(interaction, "gifs", query)

    @tree.command(name="sticker", description="Search for a sticker.")
    @app_commands.describe(query="what to search for")
    async def sticker(interaction: Interaction, query: str) -> None:
        await _search(interaction, "stickers", query)

    @tree.command(name="clip", description="Search for a short clip.")
    @app_commands.describe(query="what to search for")
    async def clip(interaction: Interaction, query: str) -> None:
        await _search(interaction, "clips", query)
