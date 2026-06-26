"""Web search tool — the bot's window onto the internet (keyless DuckDuckGo)."""

from __future__ import annotations

import asyncio
from typing import Any

from ddgs import DDGS

from mika.ai.llm.tools.registry import Tool
from mika.core.config import get_settings
from mika.core.logging import get_logger

logger = get_logger(__name__)


def _search_sync(query: str, max_results: int) -> list[dict[str, Any]]:
    return list(DDGS().text(query, max_results=max_results))


async def _web_search(args: dict[str, Any]) -> str:
    query = str(args.get("query", "")).strip()
    if not query:
        return "error: empty query"
    settings = get_settings().tools
    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(_search_sync, query, settings.web_search_max_results),
            timeout=settings.web_search_timeout,
        )
    except Exception as error:
        logger.warning("web search failed: %s", error)
        return "web search is unavailable right now"
    if not results:
        return "no results found"
    return "\n".join(
        f"- {item.get('title', '')}: {str(item.get('body', ''))[:300]} ({item.get('href', '')})"
        for item in results
    )


def web_search_tool() -> Tool:
    """Build the web-search tool the registry exposes to the model."""
    return Tool(
        name="web_search",
        description=(
            "Search the public web for current or factual information you may not "
            "know. Use it whenever asked about recent events, prices, or live facts."
        ),
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "the search query"}},
            "required": ["query"],
        },
        handler=_web_search,
    )
