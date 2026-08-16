"""Typed tool execution outcomes."""

from __future__ import annotations

from typing import Any

from mika.ai.llm.tools.registry import Tool, ToolRegistry
from mika.conversation.tools import ToolExecutor, ToolPlan


async def answer(args: dict[str, Any]) -> str:
    return f"result for {args['query']}"


async def test_executor_returns_success_for_eligible_registered_tool() -> None:
    registry = ToolRegistry()
    registry.register(Tool("web_search", "search", {}, answer))

    outcome = await ToolExecutor(registry).execute(
        ToolPlan(("web_search",), "current_fact"),
        "web_search",
        '{"query":"Berlin weather"}',
    )

    assert outcome.status == "success"
    assert outcome.summary == "result for Berlin weather"
    assert outcome.duration_ms >= 0


async def test_executor_denies_tool_not_eligible_for_turn() -> None:
    outcome = await ToolExecutor(ToolRegistry()).execute(
        ToolPlan((), "casual"),
        "web_search",
        '{"query":"anything"}',
    )

    assert outcome.status == "denied"
    assert outcome.summary == ""
    assert outcome.reason == "not_eligible"


def test_registry_schemas_filters_to_task_scoped_names() -> None:
    registry = ToolRegistry()
    registry.register(Tool("web_search", "search", {}, answer))
    registry.register(Tool("media_search", "media", {}, answer))

    schemas = registry.schemas(("media_search",))

    assert [schema["function"]["name"] for schema in schemas] == ["media_search"]
