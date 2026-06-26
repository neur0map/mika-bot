"""The settings editor: render the catalog as a form, write changes to ``.env``."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import HTMLResponse

from mika.core.env_file import read_env, write_env
from mika.web.render import page
from mika.web.settings_catalog import CATALOG, groups

router = APIRouter()

_USER_UNIT = Path.home() / ".config" / "systemd" / "user" / "mika.service"
_SYSTEM_UNIT = Path("/etc/systemd/system/mika.service")


def _is_service() -> bool:
    return _USER_UNIT.exists() or _SYSTEM_UNIT.exists()


def _form_context() -> dict[str, Any]:
    env = read_env()
    fields_by_group: dict[str, list[dict[str, Any]]] = {name: [] for name in groups()}
    for field in CATALOG:
        value = env.get(field.key, "")
        fields_by_group[field.group].append(
            {
                "key": field.key,
                "label": field.label,
                "kind": field.kind,
                "help": field.help,
                "restart": field.restart,
                "value": "" if field.kind == "secret" else value,
                "has_value": bool(value),
            }
        )
    return {"groups": groups(), "fields_by_group": fields_by_group, "is_service": _is_service()}


@router.get("/settings")
async def settings_form(request: Request) -> HTMLResponse:
    """Render the settings editor."""
    return page(request, "settings.html", active="settings", **_form_context())


@router.post("/settings")
async def settings_save(request: Request) -> HTMLResponse:
    """Persist changed fields. Secrets left blank keep their current value."""
    form = await request.form()
    current = read_env()
    updates: dict[str, str] = {}
    restart = False
    for field in CATALOG:
        if field.kind == "bool":
            value = "true" if field.key in form else "false"
        else:
            if field.key not in form:
                continue  # field not submitted -> keep current value
            value = str(form.get(field.key) or "")
            if field.kind in {"secret", "number"} and not value:
                continue  # blank secret/number -> keep current value
        if value != current.get(field.key, ""):
            updates[field.key] = value
            restart = restart or field.restart
    if updates:
        write_env(updates)
    return page(
        request,
        "settings.html",
        active="settings",
        saved=True,
        restart_pending=restart,
        **_form_context(),
    )


def _restart_command() -> str | None:
    """The shell command to restart the service, or None if no service is installed."""
    if _USER_UNIT.exists():
        return "sleep 1; systemctl --user restart mika"
    if _SYSTEM_UNIT.exists():
        return "sleep 1; sudo systemctl restart mika"
    return None


@router.post("/restart")
async def restart(request: Request) -> HTMLResponse:
    """Restart the systemd service so cached settings (token, model, keys) reload."""
    cmd = _restart_command()
    if cmd is None:
        return page(
            request,
            "settings.html",
            active="settings",
            error="No service installed - stop the bot and run it again to apply.",
            **_form_context(),
        )
    subprocess.Popen(["/bin/sh", "-c", cmd])  # noqa: S603,ASYNC220 - fixed cmd, fire-and-forget
    return page(
        request,
        "settings.html",
        active="settings",
        saved=True,
        message="Restarting - reload this page in a few seconds.",
        **_form_context(),
    )
