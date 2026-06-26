"""`mika chat`: talk to the AI from the terminal (no Discord needed)."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console

from mika.ai.llm.client import LLMClient
from mika.core.config import get_settings
from mika.persistence.engine import init_db

console = Console()


def chat(message: Annotated[str, typer.Argument(help="what to say to the bot")]) -> None:
    """Send one message to the AI and print its reply (great for testing)."""
    key = get_settings().llm.api_key
    if not key or key == "CHANGEME":
        console.print("[yellow]No AI key set.[/] Run [bold]mika setup[/] first.")
        raise typer.Exit(1)
    asyncio.run(_chat(message))


async def _chat(message: str) -> None:
    await init_db()
    client = LLMClient()
    await client.startup()
    reply = await client.reply(
        channel_id="cli", author_id="cli-user", author_name="you", text=message
    )
    console.print(reply)
