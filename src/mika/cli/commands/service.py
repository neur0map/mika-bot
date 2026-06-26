"""`mika service`: generate a systemd unit to run the bot 24/7 on a server."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _unit() -> str:
    runner = shutil.which("uv") or "uv"
    return (
        "[Unit]\n"
        "Description=Discord bot (mika)\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"WorkingDirectory={Path.cwd()}\n"
        f"ExecStart={runner} run mika run\n"
        "Restart=always\n"
        "RestartSec=10\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


@app.command()
def install() -> None:
    """Print a systemd unit (lets the bot run 24/7) and how to install it."""
    console.print(_unit())
    console.print(
        "[bold]To install:[/] save the text above as /etc/systemd/system/mika.service, then run:"
    )
    console.print("  sudo systemctl daemon-reload && sudo systemctl enable --now mika")


@app.command()
def status() -> None:
    """Show how to check the running service."""
    console.print("Check it with: [bold]systemctl status mika[/]")
    console.print("Follow logs with: [bold]journalctl -u mika -f[/]")
