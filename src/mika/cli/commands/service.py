"""`mika service`: run the bot as a background systemd service (survives reboot)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from mika.core.config import get_settings

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()

UNIT = "mika.service"
_SYSTEM_PATH = Path("/etc/systemd/system") / UNIT
_USER_PATH = Path.home() / ".config" / "systemd" / "user" / UNIT


def _root() -> bool:
    return os.geteuid() == 0


def _unit_text(user_mode: bool) -> str:
    """Build the systemd unit, anchored to the current install dir."""
    root = Path.cwd()
    exec_start = f"{root / '.venv' / 'bin' / 'mika'} run"
    wanted_by = "default.target" if user_mode else "multi-user.target"
    return (
        "[Unit]\n"
        "Description=Mika Discord bot\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"WorkingDirectory={root}\n"
        f"ExecStart={exec_start}\n"
        "Restart=always\n"
        "RestartSec=10\n\n"
        "[Install]\n"
        f"WantedBy={wanted_by}\n"
    )


def _systemctl(args: list[str], *, user_mode: bool) -> None:
    cmd = ["systemctl"]
    if user_mode:
        cmd.append("--user")
    elif not _root():
        cmd.insert(0, "sudo")  # placing/controlling a system unit needs root
    subprocess.run([*cmd, *args], check=False)


def _detect_mode() -> bool | None:
    """True = user service, False = system service, None = not installed."""
    if _USER_PATH.exists():
        return True
    if _SYSTEM_PATH.exists():
        return False
    return None


def _mode_or_exit() -> bool:
    mode = _detect_mode()
    if mode is None:
        console.print("Not installed yet - run [bold]mika service install[/] first.")
        raise typer.Exit(1)
    return mode


def _write_system_unit(text: str) -> None:
    if _root():
        _SYSTEM_PATH.write_text(text, encoding="utf-8")
        return
    # Non-root: pipe through sudo tee so the unit lands in /etc/systemd/system.
    subprocess.run(
        ["sudo", "tee", str(_SYSTEM_PATH)],
        input=text,
        text=True,
        stdout=subprocess.DEVNULL,
        check=False,
    )


@app.command()
def install(
    system: Annotated[bool, typer.Option("--system", help="system-wide (uses sudo)")] = False,
) -> None:
    """Install and start the bot as a background service that restarts on boot."""
    user_mode = not (system or _root())
    text = _unit_text(user_mode)
    if user_mode:
        _USER_PATH.parent.mkdir(parents=True, exist_ok=True)
        _USER_PATH.write_text(text, encoding="utf-8")
        _systemctl(["daemon-reload"], user_mode=True)
        _systemctl(["enable", "--now", UNIT], user_mode=True)
        subprocess.run(["loginctl", "enable-linger"], check=False)  # run without a login session
        console.print(f"[green]Installed[/] background service (user) -> {_USER_PATH}")
    else:
        _write_system_unit(text)
        _systemctl(["daemon-reload"], user_mode=False)
        _systemctl(["enable", "--now", UNIT], user_mode=False)
        console.print(f"[green]Installed[/] background service (system) -> {_SYSTEM_PATH}")
    web = get_settings().web
    panel = (
        f"\nDashboard runs with it at [bold]http://{web.host}:{web.port}[/]" if web.enabled else ""
    )
    console.print(
        "The bot now runs in the background and restarts on reboot." + panel + "\n"
        "Check: [bold]mika service status[/]   Logs: [bold]mika logs[/]   "
        "Stop: [bold]mika service stop[/]"
    )


@app.command()
def start() -> None:
    """Start the background service."""
    _systemctl(["start", UNIT], user_mode=_mode_or_exit())


@app.command()
def stop() -> None:
    """Stop the background service."""
    _systemctl(["stop", UNIT], user_mode=_mode_or_exit())


@app.command()
def restart() -> None:
    """Restart the background service (after changing settings)."""
    _systemctl(["restart", UNIT], user_mode=_mode_or_exit())


@app.command()
def status() -> None:
    """Show whether the background service is running."""
    _systemctl(["status", UNIT, "--no-pager"], user_mode=_mode_or_exit())


@app.command()
def logs(
    follow: Annotated[bool, typer.Option("--follow", "-f", help="stream live")] = False,
) -> None:
    """Show the background service's logs (from the system journal)."""
    prefix = ["--user"] if _mode_or_exit() else []
    tail = ["-f"] if follow else ["-n", "80", "--no-pager"]
    subprocess.run(["journalctl", *prefix, "-u", UNIT, *tail], check=False)


@app.command()
def uninstall() -> None:
    """Stop and remove the background service."""
    mode = _detect_mode()
    if mode is None:
        console.print("Nothing to uninstall.")
        return
    _systemctl(["disable", "--now", UNIT], user_mode=mode)
    if mode:
        _USER_PATH.unlink(missing_ok=True)
    elif _root():
        _SYSTEM_PATH.unlink(missing_ok=True)
    else:
        subprocess.run(["sudo", "rm", "-f", str(_SYSTEM_PATH)], check=False)
    _systemctl(["daemon-reload"], user_mode=mode)
    console.print("[green]Removed[/] the background service.")
