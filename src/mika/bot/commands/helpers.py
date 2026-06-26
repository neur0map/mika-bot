"""Shared building blocks for slash commands: HTTP, embeds, gates, formatting.

Network access goes through fetch_json / fetch_text / fetch_bytes so tests can
swap them for offline fakes. Call them module-qualified (helpers.fetch_json).
"""

from __future__ import annotations

from typing import Any

import discord
import httpx

from mika.core.logging import get_logger

logger = get_logger(__name__)

MAX_REPLY = 1990
_TIMEOUT = 10.0
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; discord-bot)"}


def _client(**kwargs: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS, **kwargs)


async def fetch_json(url: str, **params: Any) -> Any:
    """GET a URL and return parsed JSON."""
    async with _client() as client:
        response = await client.get(url, params=params or None)
        response.raise_for_status()
        return response.json()


async def fetch_text(url: str, **params: Any) -> str:
    """GET a URL and return the body as text."""
    async with _client() as client:
        response = await client.get(url, params=params or None)
        response.raise_for_status()
        return response.text


async def fetch_bytes(url: str) -> bytes:
    """GET a URL and return the raw body."""
    async with _client(follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def target_user(
    interaction: discord.Interaction, user: discord.User | discord.Member | None
) -> discord.User | discord.Member:
    """The chosen user, defaulting to the caller."""
    return user or interaction.user


def embed(title: str | None = None, description: str | None = None) -> discord.Embed:
    """A house-style embed."""
    return discord.Embed(title=title, description=description, color=discord.Color.blurple())


async def send(interaction: discord.Interaction, content: str = "", **kwargs: Any) -> None:
    """Reply whether or not the interaction was already deferred."""
    if content:
        kwargs["content"] = content
    if interaction.response.is_done():
        await interaction.followup.send(**kwargs)
    else:
        await interaction.response.send_message(**kwargs)


async def deny(interaction: discord.Interaction, reason: str) -> None:
    """Refuse an action with an ephemeral note."""
    await send(interaction, reason, ephemeral=True)


def is_nsfw(interaction: discord.Interaction) -> bool:
    """True only inside an age-gated channel."""
    checker = getattr(interaction.channel, "is_nsfw", None)
    return bool(checker()) if callable(checker) else False


def clip(text: str, limit: int = MAX_REPLY) -> str:
    """Trim text to fit one Discord message."""
    return text if len(text) <= limit else text[: limit - 1] + "\u2026"
