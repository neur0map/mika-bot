"""OpenAI-compatible provider (OpenRouter / Groq / Together / OpenAI / ...)."""

from __future__ import annotations

from typing import Any, cast

from openai import NOT_GIVEN, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageFunctionToolCall

from mika.ai.llm.providers.base import ChatResult, Message, ResponseFormat, ToolCall


class OpenAICompatibleProvider:
    """Talks to any OpenAI-compatible chat-completions endpoint."""

    def __init__(self, *, base_url: str, api_key: str) -> None:
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key or "missing")

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[Message] | None = None,
        temperature: float = 0.8,
        max_tokens: int = 600,
        response_format: ResponseFormat | None = None,
    ) -> ChatResult:
        tools_param: Any = tools if tools else NOT_GIVEN
        response_format_param: Any = (
            {"type": response_format}
            if isinstance(response_format, str)
            else response_format or NOT_GIVEN
        )
        response = await self._client.chat.completions.create(
            model=model,
            messages=cast("Any", messages),
            tools=tools_param,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format_param,
        )
        message = response.choices[0].message
        calls: list[ToolCall] = []
        for call in message.tool_calls or []:
            if isinstance(call, ChatCompletionMessageFunctionToolCall):
                calls.append(
                    ToolCall(id=call.id, name=call.function.name, arguments=call.function.arguments)
                )
        return ChatResult(content=message.content, tool_calls=calls)
