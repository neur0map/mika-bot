"""Turn pipeline: assemble messages, run the provider with a tool loop, return text."""

from __future__ import annotations

from mika.ai.llm.providers.base import ChatProvider, Message
from mika.ai.llm.tools.registry import ToolRegistry

_MAX_TOOL_ITERATIONS = 4


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
) -> str:
    """Drive one model turn, executing any tool calls, and return the reply text."""
    messages: list[Message] = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": user_text},
    ]
    schemas = registry.schemas() if (use_tools and registry) else None

    for _ in range(_MAX_TOOL_ITERATIONS):
        result = await provider.complete(
            messages,
            model=model,
            tools=schemas,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format="json_object" if (require_json and schemas is None) else None,
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
        response_format="json_object" if require_json else None,
    )
    return (final.content or "").strip()
