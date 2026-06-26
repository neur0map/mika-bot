"""FastAPI app: sessions + auth gate, serving the admin control panel."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_303_SEE_OTHER

from mika.core.config import get_settings
from mika.web import auth
from mika.web.routes.auth import router as auth_router
from mika.web.routes.overview import router as overview_router
from mika.web.routes.personas import router as personas_router
from mika.web.routes.settings import router as settings_router

_PUBLIC = {"/login", "/health"}


async def _guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Redirect anonymous visitors to the login page (everything is gated but /health)."""
    path = request.url.path
    if path in _PUBLIC or path.startswith("/static"):
        return await call_next(request)
    if not auth.current_user(request):
        return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
    return await call_next(request)


def create_app() -> FastAPI:
    """Build the web application (login-gated admin panel)."""
    app = FastAPI(title=get_settings().persona.name, docs_url=None, redoc_url=None)
    # Order matters: SessionMiddleware is added last so it runs first and populates
    # request.session before the auth guard reads it.
    app.add_middleware(BaseHTTPMiddleware, dispatch=_guard)
    app.add_middleware(
        SessionMiddleware, secret_key=auth.session_secret(), same_site="lax", https_only=False
    )
    app.include_router(auth_router)
    app.include_router(overview_router)
    app.include_router(settings_router)
    app.include_router(personas_router)
    return app
