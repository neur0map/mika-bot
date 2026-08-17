"""Background schedulers: the optional weekly self-reflection pass."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from discord.ext import tasks

from mika.ai.learning.reflection import auto_enabled, run_reflection
from mika.core.logging import get_logger

if TYPE_CHECKING:
    from mika.bot.client import BotApp

logger = get_logger(__name__)

_WEEK_HOURS = 168


class CancelableLoop(Protocol):
    """Minimal discord task-loop lifecycle used during shutdown."""

    def cancel(self) -> None: ...


@dataclass(slots=True)
class SchedulerLifecycle:
    """Owned scheduler handles that can be stopped during bot shutdown."""

    reflection: CancelableLoop
    relationship_job: object

    async def close(self) -> None:
        """Cancel each retained scheduler and await relationship shutdown."""
        self.reflection.cancel()
        closer = getattr(self.relationship_job, "close", None)
        if closer is not None:
            await closer()


def start_schedulers(bot: BotApp) -> SchedulerLifecycle:
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
    bot.relationship_job.start(bot.wait_until_ready)
    return SchedulerLifecycle(weekly_reflection, bot.relationship_job)
