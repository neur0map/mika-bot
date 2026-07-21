"""Deterministic guardrails for socially selective Discord actions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from time import monotonic

from mika.ai.llm.turn import MediaChoice, MikaTurn

_MEDIA_COOLDOWN_SECONDS = 90.0
_REACTION_COOLDOWN_SECONDS = 20.0
_DIRECT_FAILURE_REPLY = "i hit a snag—try me again in a sec."


@dataclass(frozen=True, slots=True)
class SocialContext:
    """Non-content signals used to decide whether a proposed action is eligible."""

    channel_id: str
    mentioned: bool
    direct_question: bool
    inbound_media_count: int


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Validated turn and optional suppression reason for aggregate telemetry."""

    turn: MikaTurn
    suppression_reason: str | None


class SocialActionPolicy:
    """Rate-limit optional media and reactions while preserving direct responses."""

    def __init__(self) -> None:
        self._last_media: dict[str, float] = {}
        self._last_reaction: dict[str, float] = {}

    def apply(
        self, turn: MikaTurn, context: SocialContext, *, now: float | None = None
    ) -> PolicyDecision:
        """Suppress repetitive optional actions and rescue direct silent turns."""
        timestamp = monotonic() if now is None else now
        result = turn
        reasons: list[str] = []
        if context.direct_question and result.is_silent:
            result = replace(result, reply=_DIRECT_FAILURE_REPLY, intent="question")
            reasons.append("direct_question_override")
        if result.media.kind != "none" and self._on_cooldown(
            self._last_media, context.channel_id, timestamp, _MEDIA_COOLDOWN_SECONDS
        ):
            result = replace(result, media=MediaChoice())
            reasons.append("media_cooldown")
        if result.reactions and self._on_cooldown(
            self._last_reaction, context.channel_id, timestamp, _REACTION_COOLDOWN_SECONDS
        ):
            result = replace(result, reactions=())
            reasons.append("reaction_cooldown")
        return PolicyDecision(result, ",".join(reasons) or None)

    def record_visible_actions(
        self, turn: MikaTurn, context: SocialContext, *, now: float | None = None
    ) -> None:
        """Record only actions that Discord actually rendered."""
        timestamp = monotonic() if now is None else now
        if turn.media.kind != "none":
            self._last_media[context.channel_id] = timestamp
        if turn.reactions:
            self._last_reaction[context.channel_id] = timestamp

    @staticmethod
    def _on_cooldown(
        history: dict[str, float], channel_id: str, now: float, cooldown: float
    ) -> bool:
        previous = history.get(channel_id)
        return previous is not None and now - previous < cooldown
