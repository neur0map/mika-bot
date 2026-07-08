"""Provider interface and result types for the LLM layer.

Messages use the OpenAI chat format (list of dicts) so tool-calling round-trips
cleanly; higher layers build them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

Message = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A function the model wants the bot to run, with raw JSON arguments."""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class ChatResult:
    """A provider response: final text, tool calls, or both."""

    content: str | None
    tool_calls: list[ToolCall]


class ChatProvider(Protocol):
    """The contract every LLM backend implements."""

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[Message] | None = None,
        temperature: float = 0.8,
        max_tokens: int = 600,
        response_format: str | None = None,
    ) -> ChatResult:
        """Return the model's reply (text and/or tool calls) for the messages."""
        ...
