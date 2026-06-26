"""`mika logs`: show recent bot logs."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from mika.core.config import get_settings

console = Console()


def logs(lines: Annotated[int, typer.Option(help="how many recent lines to show")] = 50) -> None:
    """Show the most recent log lines written by the bot."""
    path = get_settings().data_dir / "logs" / "mika.log"
    if not path.exists():
        console.print("No logs yet - start the bot with [bold]mika run[/] first.")
        raise typer.Exit(1)
    recent = path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    console.print("\n".join(recent) or "(log is empty)")
