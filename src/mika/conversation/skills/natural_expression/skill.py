"""Public orchestration for natural expression guidance."""

from __future__ import annotations

import re

from mika.conversation.skills.natural_expression.contracts import (
    EmojiProfile,
    ExpressionGuidance,
)
from mika.conversation.skills.natural_expression.human_style import HumanStyleProfile
from mika.conversation.skills.natural_expression.selector import ExpressionSelector
from mika.conversation.skills.natural_expression.situation import assess_situation
from mika.conversation.skills.natural_expression.style_ledger import StyleLedger

_EMOJI = re.compile(r"\s*(?:<a?:[^:>]+:\d+>|[\U0001F300-\U0001FAFF\u2600-\u27BF])")


class NaturalExpressionSkill:
    """Produce and enforce human-distribution-aware style advice."""

    def __init__(self, server_style: HumanStyleProfile) -> None:
        self._style = server_style
        self._ledger = StyleLedger()
        self._selector = ExpressionSelector()

    def guide(
        self,
        channel_id: str,
        text: str,
        intent: str,
        confidence: float,
        mentioned: bool,
        *,
        profiles: tuple[EmojiProfile, ...] = (),
    ) -> ExpressionGuidance:
        """Create guidance from situation, human baseline, and recent output."""
        situation = assess_situation(text, intent, confidence, mentioned)
        return self._selector.select(
            situation, self._style, self._ledger.snapshot(channel_id), profiles
        )

    def validate(self, reply: str, guidance: ExpressionGuidance) -> str:
        """Remove conspicuous model habits that the decision did not authorize."""
        cleaned = reply
        if guidance.avoid_dash:
            cleaned = re.sub(r"\s*[—\u2013]\s*", ", ", cleaned)
        if not guidance.candidates:
            cleaned = _EMOJI.sub("", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip(" ,")

    def observe(self, channel_id: str, reply: str, reactions: tuple[str, ...]) -> None:
        """Advance style state after successful output."""
        self._ledger.observe(channel_id, reply, reactions)
