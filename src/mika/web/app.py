"""FastAPI application factory serving the settings/overview page."""

from __future__ import annotations

from fastapi import FastAPI

from mika.core.config import get_settings
from mika.web.routes.overview import router as overview_router


def create_app() -> FastAPI:
    """Build the web application (read-only overview for now)."""
    app = FastAPI(title=get_settings().persona.name, docs_url=None, redoc_url=None)
    app.include_router(overview_router)
    return app
