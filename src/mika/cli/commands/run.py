"""`mika run`: start the Discord bot."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def run() -> None:
    """Start the Discord bot (bot subsystem pending)."""
    console.print("[yellow]mika run[/] is not implemented yet.")
    raise typer.Exit(1)
