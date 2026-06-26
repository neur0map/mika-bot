"""Keyless AI image generation via the free pollinations.ai service."""

from __future__ import annotations

import io
import secrets
from typing import Any
from urllib.parse import quote

import discord
from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_ENDPOINT = "https://image.pollinations.ai/prompt"
_FALLBACK = "couldn't generate that image"
_MAX_SEED = 2**31 - 1


def _build_url(prompt: str, width: int, height: int, seed: int) -> str:
    encoded = quote(prompt, safe="")
    return f"{_ENDPOINT}/{encoded}?width={width}&height={height}&nologo=true&seed={seed}"


async def _render(
    interaction: Interaction, prompt: str, width: int, height: int, seed: int
) -> None:
    """Fetch the image bytes and attach them as a PNG."""
    chosen = seed if seed > 0 else secrets.randbelow(_MAX_SEED) + 1
    try:
        data = await helpers.fetch_bytes(_build_url(prompt, width, height, chosen))
        attachment = discord.File(io.BytesIO(data), filename="art.png")
        await interaction.followup.send(file=attachment)
    except Exception as error:
        logger.warning("image generation failed: %s", error)
        await interaction.followup.send(_FALLBACK)


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the image generation commands."""

    @tree.command(name="imagine", description="Generate a 768x768 AI image from a prompt.")
    @app_commands.describe(prompt="what to draw", seed="0 for a random seed")
    async def imagine(interaction: Interaction, prompt: str, seed: int = 0) -> None:
        await interaction.response.defer()
        await _render(interaction, prompt, 768, 768, seed)

    @tree.command(name="imaginewide", description="Generate a 1024x576 widescreen AI image.")
    @app_commands.describe(prompt="what to draw")
    async def imaginewide(interaction: Interaction, prompt: str) -> None:
        await interaction.response.defer()
        await _render(interaction, prompt, 1024, 576, 0)

    @tree.command(name="imaginetall", description="Generate a 576x1024 portrait AI image.")
    @app_commands.describe(prompt="what to draw")
    async def imaginetall(interaction: Interaction, prompt: str) -> None:
        await interaction.response.defer()
        await _render(interaction, prompt, 576, 1024, 0)

    @tree.command(name="imaginesquare", description="Generate a 1024x1024 square AI image.")
    @app_commands.describe(prompt="what to draw")
    async def imaginesquare(interaction: Interaction, prompt: str) -> None:
        await interaction.response.defer()
        await _render(interaction, prompt, 1024, 1024, 0)

    @tree.command(name="avatarart", description="Generate a 512x512 avatar-style portrait.")
    @app_commands.describe(prompt="subject of the avatar")
    async def avatarart(interaction: Interaction, prompt: str) -> None:
        await interaction.response.defer()
        await _render(interaction, f"{prompt}, portrait, avatar", 512, 512, 0)
