"""`mika userbot`: run the personal user-account companion."""

from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.command()
def run() -> None:
    """Run the user-account companion (personal, ToS-grey, separate env)."""
    console.print("[yellow]mika userbot run[/] is not implemented yet.")
    console.print("Requires discord.py-self in a SEPARATE venv; it conflicts with discord-py.")
    raise typer.Exit(1)
