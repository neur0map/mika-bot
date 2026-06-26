"""`mika honcho`: run the optional long-term memory service (Docker)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console

from mika.core.config import get_settings

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()

_REPO = "https://github.com/plastic-labs/honcho.git"


def _honcho_dir() -> Path:
    return get_settings().data_dir / "honcho"


def _require_docker() -> None:
    if shutil.which("docker") is None:
        console.print("[red]Docker is required.[/] Install Docker, then run this again.")
        raise typer.Exit(1)


@app.command()
def up() -> None:
    """Fetch (first time), build, and start the Honcho memory stack."""
    _require_docker()
    path = _honcho_dir()
    if not path.exists():
        console.print("Fetching Honcho (first time only)...")
        subprocess.run(["git", "clone", "--depth", "1", _REPO, str(path)], check=True)
    compose, example = path / "docker-compose.yml", path / "docker-compose.yml.example"
    if not compose.exists() and example.exists():
        shutil.copyfile(example, compose)
    llm = get_settings().llm
    (path / ".env").write_text(
        f"AUTH_USE_AUTH=false\nLLM_OPENAI_API_KEY={llm.api_key}\nLLM_OPENAI_BASE_URL={llm.base_url}\n",
        encoding="utf-8",
    )
    console.print("Starting Honcho (the first build can take a few minutes)...")
    subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd=path, check=True)
    console.print("[green]Honcho is up.[/] Run [bold]mika doctor[/] to confirm the connection.")
    console.print("[dim]If memory derivation errors, adjust your provider in var/honcho/.env[/]")


@app.command()
def down() -> None:
    """Stop the Honcho memory stack."""
    path = _honcho_dir()
    if path.exists():
        subprocess.run(["docker", "compose", "down"], cwd=path, check=False)
    console.print("Honcho stopped.")


@app.command()
def status() -> None:
    """Show Honcho container status."""
    path = _honcho_dir()
    if not path.exists():
        console.print("Honcho isn't set up yet - run [bold]mika honcho up[/].")
        raise typer.Exit(1)
    subprocess.run(["docker", "compose", "ps"], cwd=path, check=False)
