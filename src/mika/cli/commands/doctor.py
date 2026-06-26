"""`mika doctor`: check configuration and report pass/fail per test level."""

from __future__ import annotations

import asyncio

import httpx
from rich.console import Console
from rich.table import Table

from mika.ai.llm.providers.openai_compatible import OpenAICompatibleProvider
from mika.ai.llm.tools.web_search import web_search_tool
from mika.core.config import get_settings
from mika.persistence.engine import init_db

console = Console()


def doctor() -> None:
    """Check that the bot is configured and each feature works."""
    asyncio.run(_run())


async def _check_discord() -> tuple[bool, str]:
    token = get_settings().discord.token
    if not token or token == "CHANGEME":  # noqa: S105
        return False, "no token (run mika setup)"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": f"Bot {token}"},
            )
    except Exception as error:
        return False, str(error)[:50]
    if response.is_error:
        return False, f"token rejected ({response.status_code}) - recheck it"
    return True, f"this token = bot '{response.json().get('username', '?')}'"


async def _check_db() -> tuple[bool, str]:
    try:
        await init_db()
    except Exception as error:
        return False, str(error)[:50]
    return True, "local memory ready"


async def _check_llm() -> tuple[bool, str]:
    llm = get_settings().llm
    if not llm.api_key or llm.api_key == "CHANGEME":
        return False, "no API key (run mika setup)"
    try:
        provider = OpenAICompatibleProvider(base_url=llm.base_url, api_key=llm.api_key)
        await provider.complete([{"role": "user", "content": "ok"}], model=llm.model, max_tokens=16)
    except Exception as error:
        return False, f"{type(error).__name__}: {str(error)[:45]}"
    return True, f"{llm.model} reachable"


async def _check_web() -> tuple[bool, str]:
    if not get_settings().tools.web_search_enabled:
        return True, "disabled"
    output = await web_search_tool().handler({"query": "weather today"})
    ok = not output.startswith("error") and "unavailable" not in output
    return ok, "results returned" if ok else output[:50]


async def _check_honcho() -> tuple[bool, str]:
    memory = get_settings().memory
    if not memory.honcho_enabled:
        return True, "disabled (using local memory)"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{memory.honcho_base_url}/health")
    except Exception:
        return False, "not reachable (run mika honcho up)"
    return not response.is_error, f"honcho responded {response.status_code}"


async def _run() -> None:
    rows: list[tuple[str, str, bool, str]] = [
        ("L2", "Discord token", *await _check_discord()),
        ("L3", "Memory (database)", *await _check_db()),
        ("L3", "AI / LLM", *await _check_llm()),
        ("L3", "Honcho memory", *await _check_honcho()),
        ("L4", "Web search tool", *await _check_web()),
    ]
    table = Table(title="mika doctor")
    for column in ("level", "check", "status", "detail"):
        table.add_column(column)
    for level, name, ok, detail in rows:
        table.add_row(level, name, "[green]PASS[/]" if ok else "[red]FAIL[/]", detail)
    console.print(table)
