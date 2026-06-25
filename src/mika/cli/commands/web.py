"""`mika web`: serve the localhost settings and overview page."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def web() -> None:
    """Serve the settings/overview web UI (web subsystem pending)."""
    console.print("[yellow]mika web[/] is not implemented yet.")
    raise typer.Exit(1)
