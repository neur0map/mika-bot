"""`mika run`: start the Discord bot (foreground; use `mika service` for 24/7)."""

from __future__ import annotations

from rich.console import Console

from mika.bot.client import run as run_bot

console = Console()


def run() -> None:
    """Start the bot in the foreground (Ctrl+C to stop)."""
    console.print(
        "[dim]Foreground mode - good for testing. For 24/7 in the background: "
        "[bold]mika service install[/][/]"
    )
    run_bot()
