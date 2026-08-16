"""Platform-neutral visible action and execution values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MediaRequest:
    """One requested expressive media search."""

    kind: str
    query: str


@dataclass(frozen=True, slots=True)
class ActionContext:
    """Structural signals needed by deterministic action policy."""

    channel_id: str
    mentioned: bool
    direct_question: bool
    participation_reason: str = ""


@dataclass(frozen=True, slots=True)
class ActionPlan:
    """Independent text, reaction, and media actions to attempt."""

    reply: str = ""
    reactions: tuple[str, ...] = ()
    media: MediaRequest | None = None
    silence_reason: str | None = None
    intent: str = "chat"
    confidence: float = 0.5

    @property
    def is_silent(self) -> bool:
        """Whether no visible action is planned."""
        return not self.reply.strip() and not self.reactions and self.media is None


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Only actions that Discord successfully rendered, plus stable failures."""

    reply_message_id: str | None
    applied_reactions: tuple[str, ...]
    media_url: str | None
    failures: tuple[str, ...]
