"""Situation-aware natural expression capability."""

from mika.conversation.skills.natural_expression.contracts import (
    EmojiProfile,
    ExpressionCandidate,
    ExpressionGuidance,
    SocialSituation,
    StyleSnapshot,
)
from mika.conversation.skills.natural_expression.human_style import HumanStyleProfile
from mika.conversation.skills.natural_expression.situation import assess_situation, infer_intent
from mika.conversation.skills.natural_expression.skill import NaturalExpressionSkill
from mika.conversation.skills.natural_expression.unicode_catalog import unicode_candidates

__all__ = [
    "EmojiProfile",
    "ExpressionCandidate",
    "ExpressionGuidance",
    "HumanStyleProfile",
    "NaturalExpressionSkill",
    "SocialSituation",
    "StyleSnapshot",
    "assess_situation",
    "infer_intent",
    "unicode_candidates",
]
