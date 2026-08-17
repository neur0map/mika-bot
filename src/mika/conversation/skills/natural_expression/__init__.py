"""Situation-aware natural expression capability."""

from mika.conversation.skills.natural_expression.contracts import (
    EmojiProfile,
    ExpressionCandidate,
    ExpressionGuidance,
    SocialSituation,
    StyleSnapshot,
)
from mika.conversation.skills.natural_expression.situation import assess_situation
from mika.conversation.skills.natural_expression.unicode_catalog import unicode_candidates

__all__ = [
    "EmojiProfile",
    "ExpressionCandidate",
    "ExpressionGuidance",
    "SocialSituation",
    "StyleSnapshot",
    "assess_situation",
    "unicode_candidates",
]
