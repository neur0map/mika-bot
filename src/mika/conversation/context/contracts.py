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
    fact_count: int = 0
    match_count: int = 0
    feedback_count: int = 0

    @property
    def trace_details(self) -> dict[str, object]:
        """Return counts only, never conversation content."""
        details: dict[str, object] = {
            "history_count": len(self.history),
            "avoid_phrase_count": len(self.avoid_phrases),
        }
        if self.memory or self.fact_count or self.match_count or self.feedback_count:
            details.update(
                fact_count=self.fact_count,
                match_count=self.match_count,
                feedback_count=self.feedback_count,
            )
        return details


@dataclass(frozen=True, slots=True)
class TurnObservation:
    """Visible result available for memory after Discord execution."""

    envelope: ConversationEnvelope
    reply: str
    intent: str
    confidence: float
