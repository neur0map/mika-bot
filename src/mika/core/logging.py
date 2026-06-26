"""Logging configuration. Call configure_logging() once during startup."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from rich.logging import RichHandler

from mika.core.config import get_settings

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def configure_logging(level: str = "info") -> None:
    """Install a rich console handler and a rotating file handler (var/logs/mika.log)."""
    handlers: list[logging.Handler] = [RichHandler(rich_tracebacks=True, show_path=False)]
    try:
        log_dir = get_settings().data_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "mika.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        log_format = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    except OSError:
        pass
    logging.basicConfig(
        level=_LEVELS.get(level.lower(), logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
