"""`mika learning`: control the optional self-learning system."""

from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.command()
def status() -> None:
    """Show whether self-learning is enabled and its recent activity."""
    console.print("[yellow]mika learning status[/] is not implemented yet.")
    raise typer.Exit(1)


@app.command()
def reflect() -> None:
    """Run a self-improvement reflection pass now."""
    console.print("[yellow]mika learning reflect[/] is not implemented yet.")
    raise typer.Exit(1)
