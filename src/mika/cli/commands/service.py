"""`mika service`: install and control the systemd units."""

from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()

_PENDING = "[yellow]mika service {name}[/] is not implemented yet."


@app.command()
def install() -> None:
    """Render and install the systemd units."""
    console.print(_PENDING.format(name="install"))
    raise typer.Exit(1)


@app.command()
def start() -> None:
    """Start the bot service."""
    console.print(_PENDING.format(name="start"))
    raise typer.Exit(1)


@app.command()
def stop() -> None:
    """Stop the bot service."""
    console.print(_PENDING.format(name="stop"))
    raise typer.Exit(1)


@app.command()
def status() -> None:
    """Show service status."""
    console.print(_PENDING.format(name="status"))
    raise typer.Exit(1)
