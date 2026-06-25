"""Mika command-line interface; the entry point for the `mika` command."""

from __future__ import annotations

import typer

from mika.cli.commands import run as run_cmd
from mika.cli.commands import setup as setup_cmd
from mika.cli.commands import web as web_cmd
from mika.cli.commands.service import app as service_app

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Mika - control the bot, the web UI, and the system services.",
)
app.command("run")(run_cmd.run)
app.command("web")(web_cmd.web)
app.command("setup")(setup_cmd.setup)
app.add_typer(service_app, name="service", help="Install and control the systemd services.")


def main() -> None:
    """Console-script entry point (see pyproject [project.scripts])."""
    app()
