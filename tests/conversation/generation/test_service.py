"""Provider generation, fallback, and privacy behavior."""

from __future__ import annotations

from typing import Any

from mika.ai.llm.providers.base import ChatResult, Message
from mika.ai.llm.tools.registry import ToolRegistry
from mika.conversation.generation import GenerationConfig, GenerationRequest, GenerationService
from mika.conversation.trace_service import TurnTraceService


class Provider:
    supports_tool_calls = True

    def __init__(self, result: str | Exception) -> None:
        self.result = result
        self.calls = 0

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[Message] | None = None,
        temperature: float = 0.8,
        max_tokens: int = 600,
        response_format: str | dict[str, Any] | None = None,
    ) -> ChatResult:
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return ChatResult(self.result, [])


class SequenceProvider(Provider):
    def __init__(self, results: list[str]) -> None:
        super().__init__(results[0])
        self.results = list(results)

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[Message] | None = None,
        temperature: float = 0.8,
        max_tokens: int = 600,
        response_format: str | dict[str, Any] | None = None,
    ) -> ChatResult:
        self.calls += 1
        return ChatResult(self.results.pop(0), [])


async def test_service_uses_fallback_without_tracing_raw_output() -> None:
    primary = Provider(RuntimeError("offline"))
    fallback = Provider(
        '{"reply":"still here","reactions":[],"media":{"type":"none"},'
        '"intent":"chat","confidence":0.8}'
    )
    trace = TurnTraceService("t1", "m1", "c1")
    service = GenerationService(
        primary,
        fallback,
        ToolRegistry(),
        GenerationConfig("primary", "fallback", 0.7, 200),
    )

    turn = await service.generate(GenerationRequest("system", (), "alice: hi"), trace=trace)

    assert turn.reply == "still here"
    assert primary.calls == 1
    assert fallback.calls == 1
    assert [stage.outcome for stage in trace.trace.stages] == ["fallback"]
    assert trace.trace.stages[0].details == {"provider": "fallback"}


async def test_service_repairs_one_unstructured_response_without_tools() -> None:
    provider = SequenceProvider(
        [
            "reply: almost there media: none",
            '{"reply":"clean now","reactions":[],"media":{"type":"none"},'
            '"intent":"chat","confidence":0.8}',
        ]
    )
    service = GenerationService(
        provider,
        None,
        ToolRegistry(),
        GenerationConfig("primary", "fallback", 0.7, 200),
    )

    turn = await service.generate(GenerationRequest("system", (), "alice: hi"))

    assert turn.reply == "clean now"
    assert turn.parse_status == "json"
    assert provider.calls == 2
