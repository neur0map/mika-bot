"""`mika run`: start the Discord bot."""

from __future__ import annotations

from mika.bot.client import run as run_bot


def run() -> None:
    """Start the Discord bot."""
    run_bot()
