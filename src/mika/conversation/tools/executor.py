"""Typed execution around the legacy tool registry."""

from __future__ import annotations

import time
from typing import Protocol

from mika.conversation.tools.contracts import ToolOutcome, ToolPlan


class CallableRegistry(Protocol):
    """Registry capability required by the executor."""

    async def call(self, name: str, arguments: str) -> str: ...


class ToolExecutor:
    """Execute only tools admitted by the current turn plan."""

    def __init__(self, registry: CallableRegistry) -> None:
        self._registry = registry

    async def execute(self, plan: ToolPlan, name: str, arguments: str) -> ToolOutcome:
        """Return a typed outcome without raising provider-facing exceptions."""
        if name not in plan.names:
            return ToolOutcome(name, "denied", "", 0.0, "not_eligible")
        started = time.monotonic()
        output = await self._registry.call(name, arguments)
        duration_ms = (time.monotonic() - started) * 1000
        if output.startswith("error:"):
            return ToolOutcome(name, "failure", "", duration_ms, output.removeprefix("error: "))
        return ToolOutcome(name, "success", output, duration_ms)
