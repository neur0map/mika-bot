"""Logging configuration. Call configure_logging() once during startup."""

from __future__ import annotations

import logging

from rich.logging import RichHandler

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def configure_logging(level: str = "info") -> None:
    """Install a single rich console handler at the requested level."""
    logging.basicConfig(
        level=_LEVELS.get(level.lower(), logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
