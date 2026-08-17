"""Public orchestration for natural expression guidance."""

from __future__ import annotations

import hashlib
import re

from mika.conversation.skills.natural_expression.contracts import (
    EmojiProfile,
    ExpressionGuidance,
)
from mika.conversation.skills.natural_expression.human_style import (
    HumanStyleProfile,
    blend_profiles,
)
from mika.conversation.skills.natural_expression.selector import ExpressionSelector
from mika.conversation.skills.natural_expression.situation import assess_situation
from mika.conversation.skills.natural_expression.style_ledger import StyleLedger
from mika.conversation.skills.natural_expression.unicode_catalog import unicode_candidates

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
        channel_style: HumanStyleProfile | None = None,
        person_style: HumanStyleProfile | None = None,
    ) -> ExpressionGuidance:
        """Create guidance from situation, human baseline, and recent output."""
        situation = assess_situation(text, intent, confidence, mentioned)
        style = blend_profiles(self._style, channel_style, person_style)
        if self._emoji_opportunity(channel_id, text, style.emoji_rate):
            profiles = (*profiles, *unicode_candidates(situation))
        return self._selector.select(situation, style, self._ledger.snapshot(channel_id), profiles)

    def validate(self, reply: str, guidance: ExpressionGuidance) -> str:
        """Remove conspicuous model habits that the decision did not authorize."""
        cleaned = reply
        if guidance.avoid_dash:
            cleaned = re.sub(r"\s*[—\u2013]\s*", ", ", cleaned)
        if not guidance.candidates:
            cleaned = _EMOJI.sub("", cleaned)
        if guidance.situation.intent != "serious":
            cleaned = re.sub(
                r"[.!]\s+([A-Z][a-z]*)",
                lambda match: (
                    ", " + (match.group(1) if match.group(1) == "I" else match.group(1).lower())
                ),
                cleaned,
            )
        return re.sub(r"\s+", " ", cleaned).strip(" ,")

    def observe(self, channel_id: str, reply: str, reactions: tuple[str, ...]) -> None:
        """Advance style state after successful output."""
        self._ledger.observe(channel_id, reply, reactions)

    @staticmethod
    def _emoji_opportunity(channel_id: str, text: str, rate: float) -> bool:
        """Sample sparse opportunities deterministically for stable evaluation."""
        digest = hashlib.sha256(f"{channel_id}\0{text}".encode()).digest()
        sample = int.from_bytes(digest[:4], "big") / (2**32 - 1)
        return sample < max(rate, 0.12)
