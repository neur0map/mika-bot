"""Turn pipeline: assemble messages, run the provider with a tool loop, return text."""

from __future__ import annotations

import json

from mika.ai.llm.providers.base import ChatProvider, Message
from mika.ai.llm.tools.registry import ToolRegistry
from mika.ai.llm.turn import mika_turn_response_format

_MAX_TOOL_ITERATIONS = 4
_MAX_IMAGES = 4
_SEARCH_QUERY_CHARS = 200
_RESEARCH_ATTEMPTS = 2
_MIN_FACT_CHARS = 60


def user_content(text: str, images: list[str] | None) -> str | list[Message]:
    """Build the user message body, multimodal when the message carried images.

    Uses the OpenAI content-parts shape: the HTTP providers forward it as-is, and
    the Codex provider translates it into ACP image blocks.
    """
    if not images:
        return text
    parts: list[Message] = [{"type": "text", "text": text}]
    parts.extend({"type": "image_url", "image_url": {"url": url}} for url in images[:_MAX_IMAGES])
    return parts


def _looks_like_facts(text: str) -> bool:
    """Whether a research result actually answered, or just announced itself.

    Codex sometimes ends its turn on a preamble ("I'm using the required skill
    workflow, then I'll check..."). That reads as a successful turn but contains
    nothing. A real finding carries a number or a source link; a preamble neither.
    """
    if len(text) < _MIN_FACT_CHARS:
        return False
    return "http" in text or any(char.isdigit() for char in text)


async def _lookup(provider: ChatProvider, registry: ToolRegistry, query: str) -> str:
    """Find current facts for `query`.

    A backend that can search for itself does it better than a snippet scrape, so
    prefer the provider's own `research()`; otherwise fall back to the registry's
    web_search tool.
    """
    researcher = getattr(provider, "research", None)
    if researcher is not None:
        for _ in range(_RESEARCH_ATTEMPTS):
            own: str = await researcher(query)
            if own and "NO_RESULTS" not in own and _looks_like_facts(own):
                return own
    findings = await registry.call("web_search", json.dumps({"query": query}))
    return "" if not findings or findings.startswith("error") else findings


async def _prefetch_search(
    provider: ChatProvider, registry: ToolRegistry, query: str, user_text: str
) -> str:
    """Look the facts up now and fold them into the prompt.

    Backends without function-calling can only be told facts, not asked to fetch
    them. Doing the lookup here makes current-fact answers deterministic instead
    of depending on whether the model decides to reach for its own search.
    """
    clean = query.strip()[:_SEARCH_QUERY_CHARS]
    if not clean:
        return user_text
    findings = await _lookup(provider, registry, clean)
    if not findings:
        return user_text
    return (
        f"[live lookup for {clean!r} - these are today's facts. Answer from them. "
        f"Never say you cannot check or would need to look it up: the checking is "
        f"already done and the results are right here.]\n{findings}\n\n{user_text}"
    )


async def run_turn(
    provider: ChatProvider,
    *,
    system: str,
    history: list[Message],
    user_text: str,
    registry: ToolRegistry,
    use_tools: bool,
    model: str,
    temperature: float,
    max_tokens: int,
    require_json: bool = False,
    images: list[str] | None = None,
    search_query: str = "",
) -> str:
    """Drive one model turn, executing any tool calls, and return the reply text."""
    schemas = registry.schemas() if (use_tools and registry) else None
    if schemas is not None and not provider.supports_tool_calls:
        # The backend cannot call functions, so asking it to would just be ignored.
        # Run the search here instead and hand the model the results as text.
        user_text = await _prefetch_search(provider, registry, search_query or user_text, user_text)
        schemas = None

    messages: list[Message] = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": user_content(user_text, images)},
    ]

    for _ in range(_MAX_TOOL_ITERATIONS):
        result = await provider.complete(
            messages,
            model=model,
            tools=schemas,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=mika_turn_response_format()
            if (require_json and schemas is None)
            else None,
        )
        if not result.tool_calls:
            return (result.content or "").strip()
        messages.append(
            {
                "role": "assistant",
                "content": result.content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": call.arguments},
                    }
                    for call in result.tool_calls
                ],
            }
        )
        for call in result.tool_calls:
            output = await registry.call(call.name, call.arguments)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})

    final = await provider.complete(
        messages,
        model=model,
        tools=None,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=mika_turn_response_format() if require_json else None,
    )
    return (final.content or "").strip()
