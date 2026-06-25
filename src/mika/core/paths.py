"""Filesystem paths derived from settings; ensures the data directory exists."""

from __future__ import annotations

from pathlib import Path

from mika.core.config import get_settings


def data_dir() -> Path:
    """Return the configured data directory, creating it if necessary."""
    path = get_settings().data_dir
    path.mkdir(parents=True, exist_ok=True)
    return path
