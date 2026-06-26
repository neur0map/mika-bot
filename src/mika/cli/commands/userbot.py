"""`mika userbot`: pointer to the standalone personal companion."""

from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.command()
def info() -> None:
    """Explain how to run the personal user-account companion."""
    console.print("The personal companion is a [bold]separate[/] program (it uses a")
    console.print("different Discord library that can't share this environment).")
    console.print("Run it from the [bold]userbot/[/] folder - see [bold]userbot/README.md[/].")
    console.print("[yellow]Note:[/] it automates a user account (ToS-grey); personal use only.")
