"""Chat pipeline: plain replies and the tool-calling loop."""

from __future__ import annotations

from typing import Any

from mika.ai.llm.chat.pipeline import _looks_like_facts, run_turn
from mika.ai.llm.providers.base import ChatResult, Message, ToolCall
from mika.ai.llm.tools.registry import Tool, ToolRegistry
from mika.ai.llm.turn import mika_turn_response_format


class FakeProvider:
    supports_tool_calls = True

    def __init__(self, results: list[ChatResult]) -> None:
        self._results = list(results)
        self.calls: list[list[Message]] = []
        self.calls_with_tools: list[list[Message]] = []

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
        self.calls_with_tools.append(tools or [])
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


async def test_pipeline_exposes_only_task_scoped_tool_names() -> None:
    provider = FakeProvider([ChatResult(content="ok", tool_calls=[])])
    registry = ToolRegistry()

    async def handler(args: dict[str, Any]) -> str:
        return "ok"

    registry.register(Tool("web_search", "web", {}, handler))
    registry.register(Tool("media_search", "media", {}, handler))

    await run_turn(
        provider,
        system="s",
        history=[],
        user_text="latest score",
        registry=registry,
        use_tools=True,
        tool_names=("web_search",),
        model="m",
        temperature=0.5,
        max_tokens=10,
    )

    exposed = provider.calls_with_tools[0]
    assert [schema["function"]["name"] for schema in exposed] == ["web_search"]


class NoToolCallProvider(FakeProvider):
    """A backend like Codex/ACP: it cannot be handed the caller's functions."""

    supports_tool_calls = False


async def test_search_runs_locally_when_provider_cannot_call_tools() -> None:
    provider = NoToolCallProvider([ChatResult(content="answered", tool_calls=[])])
    registry = ToolRegistry()
    seen: list[str] = []

    async def handler(args: dict[str, Any]) -> str:
        seen.append(str(args.get("query")))
        return "- Berlin: 23C partly cloudy (example.com)"

    registry.register(Tool(name="web_search", description="search", parameters={}, handler=handler))

    out = await run_turn(
        provider,
        system="s",
        history=[],
        user_text="carlos: whats the weather",
        registry=registry,
        use_tools=True,
        model="m",
        temperature=0.8,
        max_tokens=100,
        require_json=True,
        search_query="whats the weather in Berlin today",
    )

    assert out == "answered"
    # The tool ran here, not in the model's hands.
    assert seen == ["whats the weather in Berlin today"]
    prompt = provider.calls[0][-1]["content"]
    assert "23C partly cloudy" in prompt
    # Schemas are withheld: advertising tools this backend cannot call is noise.
    assert provider.response_formats == [mika_turn_response_format()]


async def test_no_local_search_when_tools_not_requested() -> None:
    provider = NoToolCallProvider([ChatResult(content="ok", tool_calls=[])])
    registry = ToolRegistry()
    called: list[str] = []

    async def handler(args: dict[str, Any]) -> str:
        called.append("ran")
        return "results"

    registry.register(Tool(name="web_search", description="search", parameters={}, handler=handler))

    await run_turn(
        provider,
        system="s",
        history=[],
        user_text="lol",
        registry=registry,
        use_tools=False,
        model="m",
        temperature=0.8,
        max_tokens=100,
    )

    assert called == []


class ResearchProvider(NoToolCallProvider):
    """A backend that can look things up better than the registry's scraper."""

    def __init__(self, results: list[ChatResult], findings: str) -> None:
        super().__init__(results)
        self.findings = findings
        self.researched: list[str] = []

    async def research(self, query: str) -> str:
        self.researched.append(query)
        return self.findings


async def test_provider_research_is_preferred_over_the_scraper() -> None:
    provider = ResearchProvider(
        [ChatResult(content="ok", tool_calls=[])],
        findings="Berlin, 14 August 2026: partly cloudy, 23C, heat warning to 19:00 CEST.",
    )
    registry = ToolRegistry()
    scraper_ran: list[str] = []

    async def handler(args: dict[str, Any]) -> str:
        scraper_ran.append("ran")
        return "- some link"

    registry.register(Tool(name="web_search", description="s", parameters={}, handler=handler))

    await run_turn(
        provider,
        system="s",
        history=[],
        user_text="carlos: weather?",
        registry=registry,
        use_tools=True,
        model="m",
        temperature=0.8,
        max_tokens=100,
        search_query="weather in Berlin",
    )

    assert provider.researched == ["weather in Berlin"]
    assert scraper_ran == []
    assert "heat warning to 19:00" in provider.calls[0][-1]["content"]


async def test_scraper_is_the_fallback_when_research_finds_nothing() -> None:
    provider = ResearchProvider([ChatResult(content="ok", tool_calls=[])], findings="NO_RESULTS")
    registry = ToolRegistry()

    async def handler(args: dict[str, Any]) -> str:
        return "- scraped fact"

    registry.register(Tool(name="web_search", description="s", parameters={}, handler=handler))

    await run_turn(
        provider,
        system="s",
        history=[],
        user_text="carlos: weather?",
        registry=registry,
        use_tools=True,
        model="m",
        temperature=0.8,
        max_tokens=100,
        search_query="weather in Berlin",
    )

    assert "scraped fact" in provider.calls[0][-1]["content"]


class FlakyResearchProvider(NoToolCallProvider):
    """Codex sometimes ends its turn on a preamble; the next attempt answers."""

    def __init__(self, results: list[ChatResult], findings: list[str]) -> None:
        super().__init__(results)
        self.findings = list(findings)
        self.attempts = 0

    async def research(self, query: str) -> str:
        self.attempts += 1
        return self.findings.pop(0)


async def test_preamble_only_research_is_retried() -> None:
    provider = FlakyResearchProvider(
        [ChatResult(content="ok", tool_calls=[])],
        findings=[
            "I'm using the required skill workflow, then I'll check live sources.",
            "Lando Norris won the 2026 Hungarian Grand Prix on July 26, 2026.",
        ],
    )
    registry = ToolRegistry()

    async def handler(args: dict[str, Any]) -> str:
        return "- weak snippet"

    registry.register(Tool(name="web_search", description="s", parameters={}, handler=handler))

    await run_turn(
        provider,
        system="s",
        history=[],
        user_text="carlos: who won?",
        registry=registry,
        use_tools=True,
        model="m",
        temperature=0.8,
        max_tokens=100,
        search_query="who won the latest F1 race",
    )

    assert provider.attempts == 2
    assert "Lando Norris" in provider.calls[0][-1]["content"]


def test_preamble_is_not_mistaken_for_facts() -> None:
    assert not _looks_like_facts("I'll go and check that for you now.")
    assert not _looks_like_facts("ok")
    assert _looks_like_facts(
        "Berlin, 14 August 2026: partly cloudy and 23C, warming to 27C this afternoon."
    )
    assert _looks_like_facts(
        "Norris won the Hungarian Grand Prix. Source: https://formula1.com/results"
    )
