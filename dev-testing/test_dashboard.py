"""The dashboard behind auth: gated pages, status API, public health probe."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from mika.core.config import get_settings
from mika.web.app import create_app


def _fresh_env() -> None:
    """Reset the throwaway .env (no owner account) and the settings cache."""
    example = Path(".env.example")
    Path(os.environ["MIKA_DOTENV"]).write_text(
        example.read_text(encoding="utf-8") if example.exists() else "", encoding="utf-8"
    )
    get_settings.cache_clear()


def _logged_in_client() -> TestClient:
    _fresh_env()
    client = TestClient(create_app())
    resp = client.post(
        "/login",
        data={"email": "me@example.com", "password": "hunter2pw", "confirm": "hunter2pw"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return client


def test_health_is_public() -> None:
    client = TestClient(create_app())
    assert client.get("/health").json()["status"] == "ok"


def test_pages_require_login() -> None:
    _fresh_env()
    client = TestClient(create_app())
    for path in ("/", "/settings", "/personas", "/api/status"):
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"


def test_dashboard_after_login() -> None:
    client = _logged_in_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "commands" in resp.text
    status = client.get("/api/status").json()
    assert status["commands"] >= 340
