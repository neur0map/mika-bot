"""Platform-neutral values exchanged by context stages."""

from __future__ import annotations

from dataclasses import dataclass

from mika.conversation.contracts import ConversationEnvelope


@dataclass(frozen=True, slots=True)
class ContextMessage:
    """One ordered message selected from channel history."""

    role: str
    author_name: str
    content: str


@dataclass(frozen=True, slots=True)
class SelectedContext:
    """Bounded evidence prepared before participation and generation."""

    history: tuple[ContextMessage, ...] = ()
    memory: str = ""
    avoid_phrases: tuple[str, ...] = ()

    @property
    def trace_details(self) -> dict[str, object]:
        """Return counts only, never conversation content."""
        return {
            "history_count": len(self.history),
            "avoid_phrase_count": len(self.avoid_phrases),
        }


@dataclass(frozen=True, slots=True)
class TurnObservation:
    """Visible result available for memory after Discord execution."""

    envelope: ConversationEnvelope
    reply: str
    intent: str
    confidence: float
