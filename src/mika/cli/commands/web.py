"""`mika web`: serve the localhost settings & overview page."""

from __future__ import annotations

import uvicorn
from rich.console import Console

from mika.core.config import get_settings

console = Console()


def web() -> None:
    """Serve the localhost overview page."""
    settings = get_settings().web
    console.print(f"overview at [bold]http://{settings.host}:{settings.port}[/] (ctrl-c to stop)")
    uvicorn.run("mika.web.app:create_app", host=settings.host, port=settings.port, factory=True)
