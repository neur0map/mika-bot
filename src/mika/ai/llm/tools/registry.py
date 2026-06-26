"""Tool registry and the JSON schema the model sees for function-calling."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from mika.ai.llm.providers.base import Message
from mika.core.logging import get_logger

logger = get_logger(__name__)

ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class Tool:
    """A callable the model may invoke, plus its advertised JSON schema."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def schema(self) -> Message:
        """Return the OpenAI function-tool schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Holds the tools available for a turn and dispatches model tool calls."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def __bool__(self) -> bool:
        return bool(self._tools)

    def schemas(self) -> list[Message]:
        return [tool.schema() for tool in self._tools.values()]

    async def call(self, name: str, arguments: str) -> str:
        """Run a tool by name with raw JSON arguments; never raises."""
        tool = self._tools.get(name)
        if tool is None:
            return f"error: unknown tool {name}"
        try:
            args = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            return "error: invalid tool arguments"
        try:
            return await tool.handler(args)
        except Exception as error:
            logger.warning("tool %s failed: %s", name, error)
            return f"error: tool {name} failed"
