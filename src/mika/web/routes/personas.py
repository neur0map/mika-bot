"""Personas: list with descriptions, one-click activate, and the CrewSoul builder."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Form
from starlette.requests import Request
from starlette.responses import HTMLResponse

from mika.ai.learning.persona_forge import (
    activate as persona_activate,
)
from mika.ai.learning.persona_forge import (
    all_personas,
    forge_persona,
    persona_summary,
)
from mika.ai.llm.client import LLMClient
from mika.core.env_file import read_env
from mika.web.render import page

router = APIRouter()


def _context() -> dict[str, Any]:
    active = read_env().get("MIKA_PERSONA_ACTIVE", "")
    personas = [
        {"name": name, "summary": persona_summary(path), "active": name == active}
        for name, path in all_personas().items()
    ]
    return {"personas": personas}


@router.get("/personas")
async def personas_page(request: Request) -> HTMLResponse:
    """List personalities and the builder."""
    return page(request, "personas.html", active="personas", **_context())


@router.post("/personas/activate")
async def activate_persona(request: Request, name: Annotated[str, Form()]) -> HTMLResponse:
    """Switch the active persona (instant; memory is untouched)."""
    if not persona_activate(name):
        return page(
            request, "personas.html", active="personas", error="Unknown persona.", **_context()
        )
    return page(
        request,
        "personas.html",
        active="personas",
        message=f"Now using {name.lower()} - new messages use it immediately.",
        **_context(),
    )


@router.post("/personas/create")
async def create(
    request: Request,
    name: Annotated[str, Form()],
    notes: Annotated[str, Form()] = "",
) -> HTMLResponse:
    """Generate a persona for a famous/fictional character via the LLM (CrewSoul)."""
    try:
        path = await forge_persona(LLMClient(), name, notes or name)
    except Exception as error:  # generation hits the network; never 500 the page
        return page(
            request,
            "personas.html",
            active="personas",
            error=f"Couldn't build that: {error}",
            **_context(),
        )
    return page(
        request,
        "personas.html",
        active="personas",
        message=f"Built {path.stem}. Click 'Use this' on its card to switch.",
        **_context(),
    )
