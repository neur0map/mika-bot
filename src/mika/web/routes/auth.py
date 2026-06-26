"""Login, first-run owner-account creation, and logout."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_303_SEE_OTHER

from mika.core.config import get_settings
from mika.core.env_file import write_env
from mika.web import auth
from mika.web.render import page

router = APIRouter()

_MIN_PASSWORD = 8


def _home() -> RedirectResponse:
    return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)


@router.get("/login")
async def login_form(request: Request) -> Response:
    """Show the sign-in form, or the create-account form on first run."""
    if auth.current_user(request):
        return _home()
    return page(request, "login.html", first_run=not auth.account_configured())


@router.post("/login")
async def login_submit(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    confirm: Annotated[str, Form()] = "",
) -> Response:
    """Create the owner account (first run) or verify credentials."""
    if not auth.account_configured():
        if password != confirm:
            return page(
                request, "login.html", first_run=True, email=email, error="Passwords do not match."
            )
        if len(password) < _MIN_PASSWORD:
            return page(
                request,
                "login.html",
                first_run=True,
                email=email,
                error="Use at least 8 characters.",
            )
        write_env({"MIKA_WEB_EMAIL": email, "MIKA_WEB_PASSWORD": auth.hash_password(password)})
        request.session["user"] = email
        return _home()
    web = get_settings().web
    if email == web.email and auth.verify_password(password, web.password):
        request.session["user"] = email
        return _home()
    return page(
        request, "login.html", first_run=False, email=email, error="Wrong email or password."
    )


@router.get("/logout")
async def logout(request: Request) -> Response:
    """Clear the session."""
    request.session.clear()
    return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)
