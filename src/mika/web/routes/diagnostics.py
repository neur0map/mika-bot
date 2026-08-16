"""Conversation diagnostics page and aggregate JSON endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import HTMLResponse

from mika.web.conversation_diagnostics import diagnostics_snapshot
from mika.web.render import page

router = APIRouter()


@router.get("/diagnostics", response_class=HTMLResponse)
async def diagnostics(request: Request) -> HTMLResponse:
    """Render aggregate engine and benchmark health without conversation content."""
    snapshot = await diagnostics_snapshot()
    return page(
        request,
        "diagnostics.html",
        active="diagnostics",
        traces=snapshot["traces"],
        benchmark=snapshot["benchmark"],
    )


@router.get("/api/diagnostics/conversation")
async def api_diagnostics() -> dict[str, Any]:
    """Return the same privacy-safe aggregates for operator automation."""
    return await diagnostics_snapshot()
