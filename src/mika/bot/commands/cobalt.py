"""Download media from a link via a cobalt instance (cobalt.tools backend)."""

from __future__ import annotations

from typing import Any

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.config import get_settings
from mika.core.logging import get_logger

logger = get_logger(__name__)

_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


def _result_url(data: Any) -> str | None:
    direct = data.get("url")
    if isinstance(direct, str):
        return direct
    picker = data.get("picker")
    if isinstance(picker, list) and picker:
        first = picker[0]
        if isinstance(first, dict) and isinstance(first.get("url"), str):
            return str(first["url"])
    return None


async def _grab(interaction: Interaction, link: str, *, audio_only: bool) -> None:
    if not link.startswith("http"):
        await helpers.deny(interaction, "give me a full https:// link")
        return
    instance = get_settings().media.cobalt_instance.rstrip("/")
    await interaction.response.defer()
    payload: dict[str, Any] = {"url": link}
    if audio_only:
        payload["downloadMode"] = "audio"
    try:
        data = await helpers.post_json(f"{instance}/", payload, headers=_HEADERS)
        url = _result_url(data)
        if url is None:
            await interaction.followup.send("couldn't get a download for that link")
            return
        await interaction.followup.send(url)
    except Exception as error:
        logger.warning("cobalt failed: %s", error)
        await interaction.followup.send(
            "the download service didn't respond. point your .env at a working cobalt "
            "instance and try again."
        )


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the download commands."""

    @tree.command(
        name="download", description="Download a video from a link (YouTube, X, TikTok...)."
    )
    @app_commands.describe(link="the media URL")
    async def download(interaction: Interaction, link: str) -> None:
        await _grab(interaction, link, audio_only=False)

    @tree.command(name="audio", description="Download just the audio from a link.")
    @app_commands.describe(link="the media URL")
    async def audio(interaction: Interaction, link: str) -> None:
        await _grab(interaction, link, audio_only=True)
