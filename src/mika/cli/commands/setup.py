"""`mika setup`: first-run setup wizard."""

from __future__ import annotations

import shutil
from pathlib import Path

from rich.console import Console

console = Console()


def setup() -> None:
    """Ensure a .env exists and point the operator at the next steps."""
    env, example = Path(".env"), Path(".env.example")
    if not env.exists() and example.exists():
        shutil.copyfile(example, env)
        console.print("Created [bold].env[/] from template.")
    else:
        console.print(".env already present; leaving it untouched.")
    console.print("Edit [bold].env[/] (Discord token, LLM key), then run [bold]mika run[/].")
    console.print("The full interactive wizard ships with the web/config subsystems.")
