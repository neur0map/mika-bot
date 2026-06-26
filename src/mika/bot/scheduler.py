"""Background schedulers: the optional weekly self-reflection pass."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from discord.ext import tasks

from mika.ai.learning.reflection import auto_enabled, run_reflection
from mika.core.logging import get_logger

if TYPE_CHECKING:
    from mika.bot.client import BotApp

logger = get_logger(__name__)

_WEEK_HOURS = 168


def start_schedulers(bot: BotApp) -> None:
    """Start background loops once the bot is ready."""

    @tasks.loop(hours=_WEEK_HOURS)
    async def weekly_reflection() -> None:
        if await auto_enabled():
            with contextlib.suppress(Exception):
                await run_reflection(bot.llm)

    @weekly_reflection.before_loop
    async def _wait_ready() -> None:
        await bot.wait_until_ready()

    weekly_reflection.start()
