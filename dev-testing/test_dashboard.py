"""The localhost dashboard: status API, HTML page and health probe."""

from __future__ import annotations

from fastapi.testclient import TestClient

from mika.web.app import create_app


def test_status_api_reports_commands() -> None:
    client = TestClient(create_app())
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["commands"] >= 340
    assert len(data["groups"]) > 10


def test_dashboard_html_renders() -> None:
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "commands" in response.text


def test_health() -> None:
    client = TestClient(create_app())
    assert client.get("/health").json()["status"] == "ok"
