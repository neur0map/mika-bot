"""Chat pipeline: plain replies and the tool-calling loop."""

from __future__ import annotations

from typing import Any

from mika.ai.llm.chat.pipeline import run_turn
from mika.ai.llm.providers.base import ChatResult, Message, ToolCall
from mika.ai.llm.tools.registry import Tool, ToolRegistry
from mika.ai.llm.turn import mika_turn_response_format


class FakeProvider:
    def __init__(self, results: list[ChatResult]) -> None:
        self._results = list(results)
        self.calls: list[list[Message]] = []

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
        self.calls.append(messages)
        self.response_formats = [*getattr(self, "response_formats", []), response_format]
        return self._results.pop(0)


async def test_plain_reply() -> None:
    provider = FakeProvider([ChatResult(content="hello", tool_calls=[])])
    out = await run_turn(
        provider,
        system="s",
        history=[],
        user_text="hi",
        registry=ToolRegistry(),
        use_tools=False,
        model="m",
        temperature=0.5,
        max_tokens=10,
    )
    assert out == "hello"


async def test_tool_loop_runs_tool_then_answers() -> None:
    async def _tool(_args: dict[str, Any]) -> str:
        return "the answer is 42"

    registry = ToolRegistry()
    registry.register(Tool(name="t", description="d", parameters={}, handler=_tool))
    provider = FakeProvider(
        [
            ChatResult(content=None, tool_calls=[ToolCall(id="1", name="t", arguments="{}")]),
            ChatResult(content="done", tool_calls=[]),
        ]
    )
    out = await run_turn(
        provider,
        system="s",
        history=[],
        user_text="hi",
        registry=registry,
        use_tools=True,
        model="m",
        temperature=0.5,
        max_tokens=10,
    )
    assert out == "done"
    assert any(message.get("role") == "tool" for message in provider.calls[1])


async def test_json_mode_is_requested_without_tools() -> None:
    provider = FakeProvider([ChatResult(content='{"reply":"ok"}', tool_calls=[])])
    out = await run_turn(
        provider,
        system="s",
        history=[],
        user_text="hi",
        registry=ToolRegistry(),
        use_tools=False,
        model="m",
        temperature=0.5,
        max_tokens=10,
        require_json=True,
    )
    assert out == '{"reply":"ok"}'
    assert provider.response_formats == [mika_turn_response_format()]
