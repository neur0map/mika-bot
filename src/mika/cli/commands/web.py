"""`mika web`: serve the localhost settings & overview page."""

from __future__ import annotations

import uvicorn
from rich.console import Console

from mika.core.config import get_settings

console = Console()


def web() -> None:
    """Serve the dashboard on its own (the bot already serves it while running)."""
    settings = get_settings().web
    console.print(
        f"dashboard at [bold]http://{settings.host}:{settings.port}[/] (ctrl-c to stop)\n"
        "[dim]note: `mika run` and the service already serve this - use this only "
        "to view the panel without the bot.[/]"
    )
    uvicorn.run("mika.web.app:create_app", host=settings.host, port=settings.port, factory=True)
