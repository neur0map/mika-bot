"""Overview route: bot status and configuration at a glance."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from mika.core.config import get_settings

router = APIRouter()

_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>{name}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:640px;margin:3rem auto;padding:0 1rem}}
h1{{font-weight:600}} table{{width:100%;border-collapse:collapse}}
td{{padding:.5rem;border-bottom:1px solid #eee}} td:first-child{{color:#666}}
</style></head><body><h1>{name}</h1><p>status: running</p>
<table>{rows}</table></body></html>"""


@router.get("/", response_class=HTMLResponse)
async def overview() -> str:
    """Render a read-only status/configuration page."""
    settings = get_settings()
    data = {
        "Bot name": settings.persona.name,
        "Environment": settings.env,
        "AI model": settings.llm.model,
        "Memory window": str(settings.memory.recent_window),
        "Honcho memory": "on" if settings.memory.honcho_enabled else "off",
        "Web search": "on" if settings.tools.web_search_enabled else "off",
    }
    rows = "".join(f"<tr><td>{key}</td><td>{value}</td></tr>" for key, value in data.items())
    return _PAGE.format(name=settings.persona.name, rows=rows)


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
