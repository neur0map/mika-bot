"""Read and update the ``.env`` file in place without disturbing its layout.

Shared by the setup wizard and the web settings page so configuration is written
one way. Updates known keys where they sit; appends anything new at the end. The path
matches config (``MIKA_DOTENV`` env var, default ``.env`` relative to the working dir).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from mika.core.config import get_settings

_LINE = re.compile(r"^([A-Z][A-Z0-9_]+)=(.*)$")


def _env() -> Path:
    return Path(os.environ.get("MIKA_DOTENV", ".env"))


def read_env() -> dict[str, str]:
    """Return the current ``.env`` as a key/value mapping (missing file -> empty)."""
    path = _env()
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _LINE.match(line)
            if match:
                out[match.group(1)] = match.group(2)
    return out


def write_env(updates: dict[str, str]) -> None:
    """Apply ``key=value`` updates, preserving layout. Templates from ``.env.example``."""
    env = _env()
    base = env if env.exists() else Path(".env.example")
    lines = base.read_text(encoding="utf-8").splitlines() if base.exists() else []
    written: set[str] = set()
    out: list[str] = []
    for line in lines:
        match = _LINE.match(line)
        if match and match.group(1) in updates:
            out.append(f"{match.group(1)}={updates[match.group(1)]}")
            written.add(match.group(1))
        else:
            out.append(line)
    out.extend(f"{key}={value}" for key, value in updates.items() if key not in written)
    env.write_text("\n".join(out) + "\n", encoding="utf-8")
    get_settings.cache_clear()  # the running process (incl. the in-bot web) sees fresh values
