"""Tool registry: registration, dispatch, and error handling."""

from __future__ import annotations

from typing import Any

from mika.ai.llm.tools.registry import Tool, ToolRegistry


async def _echo(args: dict[str, Any]) -> str:
    return f"echo:{args.get('x')}"


def _tool() -> Tool:
    return Tool(name="echo", description="d", parameters={}, handler=_echo)


async def test_registry_dispatches_and_reports_emptiness() -> None:
    registry = ToolRegistry()
    assert not registry
    registry.register(_tool())
    assert registry
    assert await registry.call("echo", '{"x": "hi"}') == "echo:hi"


async def test_registry_handles_bad_input() -> None:
    registry = ToolRegistry()
    registry.register(_tool())
    assert "unknown" in await registry.call("missing", "{}")
    assert "invalid" in await registry.call("echo", "{not json")
