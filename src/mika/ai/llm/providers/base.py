"""Provider interface. Every LLM backend implements ChatProvider."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A single message in a conversation sent to a provider."""

    role: str
    content: str


class ChatProvider(Protocol):
    """The minimal contract every provider adapter must satisfy."""

    async def complete(self, messages: list[ChatMessage], *, model: str) -> str:
        """Return the model's reply text for the given messages."""
        ...
