"""Dashboard overview + machine-readable status + health probe."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import HTMLResponse

from mika.core.config import get_settings
from mika.core.env_file import read_env
from mika.web.render import page

router = APIRouter()


def _status() -> dict[str, Any]:
    settings = get_settings()
    return {
        "name": settings.persona.name,
        "conversation_only": True,
        "model": settings.llm.model,
        "memory": "honcho + local" if settings.memory.honcho_enabled else "local",
        "web_search": settings.tools.web_search_enabled,
        "gif_search": bool(settings.media.klipy_api_key),
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render the conversation-health overview dashboard."""
    data = _status()
    active = read_env().get("MIKA_PERSONA_ACTIVE") or str(data["name"])
    return page(
        request,
        "overview.html",
        active="overview",
        model_short=str(data["model"]).split("/")[-1].upper(),
        memory_short="HONCHO" if str(data["memory"]).startswith("honcho") else "LOCAL",
        persona_active=active,
        gif_search=bool(data["gif_search"]),
    )


@router.get("/api/status")
async def api_status() -> dict[str, Any]:
    """Machine-readable bot status."""
    return _status()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe (public - no auth)."""
    return {"status": "ok"}
