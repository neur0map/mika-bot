"""Anti-spam detection: rate limits and content filters, driven by per-guild config."""

from __future__ import annotations

import contextlib
import re
import time
from datetime import timedelta

import discord

from mika.persistence.repositories.config import all_settings

_INVITE_RE = re.compile(r"discord(?:app)?\.(?:gg|com/invite)/", re.IGNORECASE)
_LINK_RE = re.compile(r"https?://", re.IGNORECASE)
_CAPS_MIN = 10
_CAPS_RATIO = 0.7
_TIMEOUT_MINUTES = 5
_RECENT: dict[tuple[int, int], list[float]] = {}


def _too_many_caps(content: str) -> bool:
    letters = [char for char in content if char.isalpha()]
    if len(letters) < _CAPS_MIN:
        return False
    caps = sum(1 for char in letters if char.isupper())
    return caps / len(letters) > _CAPS_RATIO


def _rate_exceeded(guild_id: int, user_id: int, limit: int, window: float) -> bool:
    now = time.monotonic()
    key = (guild_id, user_id)
    recent = [stamp for stamp in _RECENT.get(key, []) if now - stamp < window]
    recent.append(now)
    _RECENT[key] = recent
    return len(recent) > limit


def check(message: discord.Message, config: dict[str, str]) -> str | None:
    """Return a violation reason for a message, or None if it's fine."""
    if config.get("filter_invites") == "1" and _INVITE_RE.search(message.content):
        return "invite links aren't allowed here"
    if config.get("filter_links") == "1" and _LINK_RE.search(message.content):
        return "links aren't allowed here"
    if config.get("filter_caps") == "1" and _too_many_caps(message.content):
        return "please don't shout"
    max_mentions = config.get("max_mentions", "")
    if max_mentions.isdigit() and len(message.mentions) > int(max_mentions):
        return "too many mentions"
    if config.get("antispam_enabled") == "1":
        limit = int(config.get("antispam_rate") or "5")
        window = float(config.get("antispam_window") or "5")
        if _rate_exceeded(message.guild.id, message.author.id, limit, window):  # type: ignore[union-attr]
            return "you're sending messages too fast"
    return None


async def enforce(message: discord.Message) -> str | None:
    """Inspect a message and act on any violation. Returns the reason, if any."""
    guild = message.guild
    if guild is None or message.author.bot:
        return None
    config = await all_settings(guild.id)
    if not config:
        return None
    reason = check(message, config)
    if reason is None:
        return None
    with contextlib.suppress(discord.HTTPException):
        await message.delete()
    author = message.author
    if config.get("antispam_action") == "timeout" and isinstance(author, discord.Member):
        with contextlib.suppress(discord.HTTPException):
            await author.timeout(timedelta(minutes=_TIMEOUT_MINUTES), reason="anti-spam")
    with contextlib.suppress(discord.HTTPException):
        await message.channel.send(f"{author.mention} {reason}", delete_after=5)
    return reason
