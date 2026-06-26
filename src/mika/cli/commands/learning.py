"""`mika learning`: the optional self-learning system."""

from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.command()
def status() -> None:
    """Show the self-learning status."""
    console.print("Self-learning is scaffolded but not active in this build.")
    console.print("The bot already remembers via local + Honcho memory - check `mika doctor`.")
