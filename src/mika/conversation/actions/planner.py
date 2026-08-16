"""Deterministic cooldown and direct-response action policy."""

from __future__ import annotations

from time import monotonic

from mika.ai.llm.turn import MikaTurn
from mika.conversation.actions.contracts import (
    ActionContext,
    ActionPlan,
    ExecutionResult,
    MediaRequest,
)

_MEDIA_COOLDOWN = 90.0
_REACTION_COOLDOWN = 20.0
_DIRECT_FAILURE_REPLY = "i hit a snag—try me again in a sec."
_PROACTIVE_MEDIA = {
    "proactive_media_celebration": "celebration hype reaction",
    "proactive_media_punchline": "developer joke reaction",
}


class ActionPlanner:
    """Apply independent cooldowns and rescue directly addressed silence."""

    def __init__(self) -> None:
        self._last_media: dict[str, float] = {}
        self._last_reaction: dict[str, float] = {}

    def plan(
        self, turn: MikaTurn, context: ActionContext, *, now: float | None = None
    ) -> ActionPlan:
        """Convert a candidate into actions eligible at this moment."""
        timestamp = monotonic() if now is None else now
        reply = turn.reply
        if context.direct_question and turn.is_silent:
            reply = _DIRECT_FAILURE_REPLY
        reactions = turn.reactions
        if reactions and self._on_cooldown(
            self._last_reaction, context.channel_id, timestamp, _REACTION_COOLDOWN
        ):
            reactions = ()
        media = MediaRequest(turn.media.kind, turn.media.query) if turn.media.query else None
        if media is None and context.participation_reason in _PROACTIVE_MEDIA:
            media = MediaRequest("gif", _PROACTIVE_MEDIA[context.participation_reason])
        if media is not None and self._on_cooldown(
            self._last_media, context.channel_id, timestamp, _MEDIA_COOLDOWN
        ):
            media = None
        silent = not reply.strip() and not reactions and media is None
        return ActionPlan(
            reply=reply,
            reactions=reactions,
            media=media,
            silence_reason="model_silence" if silent else None,
            intent="question" if reply == _DIRECT_FAILURE_REPLY else turn.intent,
            confidence=turn.confidence,
        )

    def record_visible(
        self,
        plan: ActionPlan,
        execution: ExecutionResult,
        *,
        channel_id: str,
        now: float | None = None,
    ) -> None:
        """Advance cooldowns only for actions Discord actually rendered."""
        timestamp = monotonic() if now is None else now
        if execution.applied_reactions:
            self._last_reaction[channel_id] = timestamp
        if execution.media_url is not None:
            self._last_media[channel_id] = timestamp

    @staticmethod
    def _on_cooldown(
        history: dict[str, float], channel_id: str, now: float, cooldown: float
    ) -> bool:
        previous = history.get(channel_id)
        return previous is not None and now - previous < cooldown
