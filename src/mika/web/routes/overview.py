"""Dashboard overview + machine-readable status + health probe."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import discord
from discord import app_commands
from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import HTMLResponse

from mika.bot.commands import register_all
from mika.core.config import get_settings
from mika.core.env_file import read_env
from mika.web.render import page

router = APIRouter()


@lru_cache(maxsize=1)
def _command_stats() -> tuple[int, list[tuple[str, str, int]]]:
    client = discord.Client(intents=discord.Intents.none())
    tree = app_commands.CommandTree(client)
    register_all(tree)
    total = 0
    groups: list[tuple[str, str, int]] = []
    for command in tree.get_commands():
        if isinstance(command, app_commands.Group):
            count = sum(
                1 for sub in command.walk_commands() if isinstance(sub, app_commands.Command)
            )
            groups.append((command.name, command.description, count))
            total += count
        else:
            total += 1
    return total, sorted(groups)


def _status() -> dict[str, Any]:
    settings = get_settings()
    total, groups = _command_stats()
    return {
        "name": settings.persona.name,
        "commands": total,
        "groups": [{"name": n, "description": d, "count": c} for n, d, c in groups],
        "model": settings.llm.model,
        "memory": "honcho + local" if settings.memory.honcho_enabled else "local",
        "web_search": settings.tools.web_search_enabled,
        "gif_search": bool(settings.media.klipy_api_key),
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render the overview dashboard."""
    data = _status()
    active = read_env().get("MIKA_PERSONA_ACTIVE") or str(data["name"])
    return page(
        request,
        "overview.html",
        active="overview",
        commands=data["commands"],
        groups=data["groups"],
        model_short=str(data["model"]).split("/")[-1].upper(),
        memory_short="HONCHO" if str(data["memory"]).startswith("honcho") else "LOCAL",
        persona_active=active,
    )


@router.get("/api/status")
async def api_status() -> dict[str, Any]:
    """Machine-readable bot status."""
    return _status()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe (public - no auth)."""
    return {"status": "ok"}
