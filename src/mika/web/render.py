"""Jinja2 template wiring + a small helper that injects common page context."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import HTMLResponse

from mika.core.config import get_settings

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def page(request: Request, name: str, *, active: str = "", **context: Any) -> HTMLResponse:
    """Render a template with the bot name + active-nav marker already supplied."""
    base = {"name": get_settings().persona.name, "active": active}
    return templates.TemplateResponse(request, name, {**base, **context})
