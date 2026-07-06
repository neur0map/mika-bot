"""Gateway event handlers. One file per event; wired by register_events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mika.bot.events import antispam, members, message, reactions, ready

if TYPE_CHECKING:
    from mika.bot.client import BotApp

__all__ = ["register_events"]


def register_events(bot: BotApp) -> None:
    """Attach every event handler to the bot."""
    ready.setup(bot)
    message.setup(bot)
    reactions.setup(bot)
    members.setup(bot)
    antispam.setup(bot)
