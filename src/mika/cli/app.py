"""Mika command-line interface; the entry point for the `mika` command."""

from __future__ import annotations

import typer

from mika.cli.commands import run as run_cmd
from mika.cli.commands import setup as setup_cmd
from mika.cli.commands import web as web_cmd
from mika.cli.commands.learning import app as learning_app
from mika.cli.commands.service import app as service_app
from mika.cli.commands.userbot import app as userbot_app

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Mika - control the bot, the web UI, and the system services.",
)
app.command("run")(run_cmd.run)
app.command("web")(web_cmd.web)
app.command("setup")(setup_cmd.setup)
app.add_typer(service_app, name="service", help="Install and control the systemd services.")
app.add_typer(
    userbot_app, name="userbot", help="Run the personal user-account companion (separate env)."
)
app.add_typer(learning_app, name="learning", help="Control the optional self-learning system.")


def main() -> None:
    """Console-script entry point (see pyproject [project.scripts])."""
    app()
