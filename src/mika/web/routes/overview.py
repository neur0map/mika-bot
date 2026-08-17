"""Dashboard overview + machine-readable status + health probe."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import HTMLResponse

from mika.core.config import get_settings
from mika.core.env_file import read_env
from mika.persistence.conversations.relationship_memory import RelationshipMemoryRepository
from mika.persistence.conversations.relationship_records import RelationshipMemoryStatus
from mika.persistence.engine import session
from mika.web.render import page

router = APIRouter()


async def _relationship_snapshot() -> RelationshipMemoryStatus:
    async with session() as active:
        return await RelationshipMemoryRepository(active).status()


async def _status() -> dict[str, Any]:
    settings = get_settings()
    result: dict[str, Any] = {
        "name": settings.persona.name,
        "conversation_only": True,
        "model": settings.llm.model,
        "memory": "honcho + local" if settings.memory.honcho_enabled else "local",
        "web_search": settings.tools.web_search_enabled,
        "gif_search": bool(settings.media.klipy_api_key),
    }
    try:
        snapshot = await _relationship_snapshot()
    except Exception:
        result["relationship_memory"] = {"degraded": True}
        return result
    result["relationship_memory"] = {
        "claims": snapshot.claim_count,
        "candidates": snapshot.candidate_count,
        "profiles": snapshot.active_profile_count,
        "recalls": snapshot.recall_count,
        "policy_version": snapshot.active_policy_version_id,
        "learning_enabled": snapshot.learning_enabled,
        "last_consolidation_at": _iso(snapshot.last_consolidation_at),
        "archive": {
            "source": snapshot.archive_source_name,
            "message_id": snapshot.archive_message_id,
            "updated_at": _iso(snapshot.archive_updated_at),
        },
        "operation_health": snapshot.operation_health,
        "degraded": False,
    }
    return result


def _iso(value: object) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render the conversation-health overview dashboard."""
    data = await _status()
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
    return await _status()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe (public - no auth)."""
    return {"status": "ok"}
