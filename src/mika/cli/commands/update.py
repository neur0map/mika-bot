"""`mika update <zip>`: safely update to a new release, keeping your config and data.

Swaps in the new code, leaves ``.env``, ``var/`` (memory, database, logs) and your
active persona untouched, re-syncs dependencies, and restarts the service so new
commands sync to Discord. A backup is written first so an update can be rolled back.
"""

from __future__ import annotations

import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from mika.core.paths import data_dir

console = Console()

# Code/config the update replaces; everything else (.env, var/) is left alone.
_BACKUP = (
    "src",
    "config",
    "docs",
    "pyproject.toml",
    "uv.lock",
    "Makefile",
    "install.sh",
    "update.sh",
    "README.md",
    "ARCHITECTURE.md",
    ".env.example",
    ".python-version",
    "Dockerfile",
    "docker-compose.yml",
)
_NEVER_TOUCH = {".env", "var", ".git", ".venv"}


def _version(pyproject: Path) -> str:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return str(data.get("project", {}).get("version", "?"))


def _find_release(extracted: Path) -> Path:
    """The release lives in a single top-level dir (mika-X.Y.Z/). Find it."""
    if (extracted / "pyproject.toml").exists():
        return extracted
    dirs = [d for d in extracted.iterdir() if d.is_dir()]
    for d in dirs:
        if (d / "pyproject.toml").exists() and (d / "src" / "mika").is_dir():
            return d
    raise typer.BadParameter("that zip does not look like a mika release")


def _backup(root: Path) -> Path:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    archive = data_dir() / "backups" / f"pre-update-{stamp}.tgz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as tar:
        for name in _BACKUP:
            path = root / name
            if path.exists():
                tar.add(path, arcname=name)
    return archive


def _apply(release: Path, root: Path) -> None:
    """Copy new code in. Replace code dirs cleanly; merge config but keep the active persona."""
    for item in sorted(release.iterdir()):
        if item.name in _NEVER_TOUCH:
            continue
        dest = root / item.name
        if item.name == "config" and item.is_dir():
            shutil.copytree(
                item, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("persona.md")
            )
        elif item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)


def _restore(backup: Path, root: Path) -> None:
    with tarfile.open(backup, "r:gz") as tar:
        tar.extractall(root)  # noqa: S202 - our own backup, written moments ago


def _restart() -> str | None:
    user = Path.home() / ".config" / "systemd" / "user" / "mika.service"
    if user.exists():
        subprocess.run(["systemctl", "--user", "restart", "mika"], check=False)
        return "service restarted"
    if Path("/etc/systemd/system/mika.service").exists():
        subprocess.run(["sudo", "systemctl", "restart", "mika"], check=False)
        return "service restarted"
    return None


def update(
    zip_path: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, help="the new mika-X.Y.Z.zip")
    ],
) -> None:
    """Update to a new release zip - your settings, memory and persona are kept."""
    root = Path.cwd()
    if not (root / "pyproject.toml").exists() or not (root / "src" / "mika").is_dir():
        console.print("[red]Run this from your bot's folder (where you installed it).[/]")
        raise typer.Exit(1)

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as bundle:
            bundle.extractall(tmp)  # noqa: S202 - the operator's own update zip
        release = _find_release(Path(tmp))
        old, new = _version(root / "pyproject.toml"), _version(release / "pyproject.toml")
        console.print(f"Updating [bold]{old}[/] -> [bold]{new}[/] ...")

        backup = _backup(root)
        console.print(f"[dim]Backed up current version to {backup}[/]")
        try:
            _apply(release, root)
        except Exception as error:
            console.print(f"[red]Update failed ({error}); restoring backup...[/]")
            _restore(backup, root)
            raise typer.Exit(1) from error

    if shutil.which("uv"):
        console.print("Syncing dependencies...")
        subprocess.run(["uv", "sync", "--no-dev"], check=False)
    else:
        console.print("[yellow]uv not found - run 'uv sync --no-dev' yourself.[/]")

    note = _restart()
    done = f"[green]Updated to {new}.[/]"
    done += f" {note}." if note else " Restart the bot to finish (mika run, or your service)."
    console.print(done)
    console.print(f"[dim]Roll back with: tar xzf {backup} (from this folder)[/]")
