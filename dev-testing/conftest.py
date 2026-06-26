"""Shared fixtures. Forces command HTTP offline so the suite is deterministic."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

_TEST_DB = Path("/tmp/mika-devtest.sqlite3")
_TEST_DB.unlink(missing_ok=True)
os.environ["MIKA_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB}"
os.environ["MIKA_PERSONA_FILE"] = "/tmp/mika-devtest-persona.md"

# Point config + the env writer at a throwaway .env so tests never touch the real one.
_TEST_ENV = Path("/tmp/mika-devtest.env")
_EXAMPLE = Path(".env.example")
_TEST_ENV.write_text(
    _EXAMPLE.read_text(encoding="utf-8") if _EXAMPLE.exists() else "", encoding="utf-8"
)
os.environ["MIKA_DOTENV"] = str(_TEST_ENV)

sys.path.insert(0, str(Path(__file__).parent))

from mika.bot.commands import helpers  # noqa: E402

_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000154a24f6f0000000049454e44ae426082"
)


class _Any:
    """Stands in for arbitrary JSON: any access yields something usable."""

    def __getitem__(self, key: Any) -> _Any:
        return self

    def __getattr__(self, name: str) -> _Any:
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> _Any:
        return self

    def __iter__(self) -> Any:
        return iter([self])

    def get(self, *args: Any, **kwargs: Any) -> _Any:
        return self

    def __str__(self) -> str:
        return "https://example.com/x.png"

    def __int__(self) -> int:
        return 0

    def __float__(self) -> float:
        return 0.0

    def __len__(self) -> int:
        return 1

    def __bool__(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_json(*args: Any, **kwargs: Any) -> _Any:
        return _Any()

    async def fake_text(*args: Any, **kwargs: Any) -> str:
        return "fake response text"

    async def fake_bytes(*args: Any, **kwargs: Any) -> bytes:
        return _PNG

    monkeypatch.setattr(helpers, "fetch_json", fake_json)
    monkeypatch.setattr(helpers, "fetch_text", fake_text)
    monkeypatch.setattr(helpers, "fetch_bytes", fake_bytes)
    monkeypatch.setattr(helpers, "post_json", fake_json)
