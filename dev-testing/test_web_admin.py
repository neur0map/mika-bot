"""Web admin: login flow, settings save (writes .env), persona activate."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from mika.core.config import get_settings
from mika.core.env_file import read_env
from mika.web.app import create_app


def _reset() -> None:
    example = Path(".env.example")
    Path(os.environ["MIKA_DOTENV"]).write_text(
        example.read_text(encoding="utf-8") if example.exists() else "", encoding="utf-8"
    )
    get_settings.cache_clear()


def _owner_client() -> TestClient:
    _reset()
    client = TestClient(create_app())
    client.post(
        "/login",
        data={"email": "owner@local", "password": "longenough", "confirm": "longenough"},
    )
    return client


def test_first_run_creates_account_then_requires_password() -> None:
    _reset()
    client = TestClient(create_app())
    assert "Create your account" in client.get("/login").text
    client.post(
        "/login", data={"email": "owner@local", "password": "longenough", "confirm": "longenough"}
    )
    assert read_env()["MIKA_WEB_EMAIL"] == "owner@local"
    # a fresh client (no cookie) is now asked to sign in, and a wrong password is rejected
    other = TestClient(create_app())
    bad = other.post("/login", data={"email": "owner@local", "password": "wrong"})
    assert "Wrong email or password" in bad.text


def test_password_mismatch_is_rejected() -> None:
    _reset()
    client = TestClient(create_app())
    resp = client.post("/login", data={"email": "a@b", "password": "longenough", "confirm": "nope"})
    assert "do not match" in resp.text
    assert "MIKA_WEB_EMAIL" not in read_env()


def test_settings_save_writes_env() -> None:
    client = _owner_client()
    client.post("/settings", data={"MIKA_LLM_MODEL": "anthropic/claude-3.5-sonnet"})
    assert read_env()["MIKA_LLM_MODEL"] == "anthropic/claude-3.5-sonnet"


def test_secret_left_blank_is_kept() -> None:
    client = _owner_client()
    client.post("/settings", data={"DISCORD_TOKEN": "secret-token-123"})
    client.post("/settings", data={"DISCORD_TOKEN": ""})  # blank -> keep
    assert read_env()["DISCORD_TOKEN"] == "secret-token-123"


def test_persona_activate_sets_active() -> None:
    client = _owner_client()
    resp = client.post("/personas/activate", data={"name": "friendly"})
    assert resp.status_code == 200
    assert read_env()["MIKA_PERSONA_ACTIVE"] == "friendly"
    assert Path(get_settings().persona.file).read_text(encoding="utf-8").startswith("# Persona")
