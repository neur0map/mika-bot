"""Rank expression candidates against human style priors."""

from __future__ import annotations

from mika.conversation.skills.natural_expression.contracts import (
    EmojiProfile,
    ExpressionCandidate,
    ExpressionGuidance,
    SocialSituation,
    StyleSnapshot,
)
from mika.conversation.skills.natural_expression.human_style import HumanStyleProfile

_MIN_CANDIDATE_SCORE = 0.72
_STRONG_CONTEXT_CONFIDENCE = 0.88
_REPEAT_OVERRIDE_CONFIDENCE = 0.97
_RARE_DASH_RATE = 0.01


class ExpressionSelector:
    """Prefer abstention unless context and semantic evidence are both strong."""

    def select(
        self,
        situation: SocialSituation,
        style: HumanStyleProfile,
        snapshot: StyleSnapshot,
        profiles: tuple[EmojiProfile, ...],
    ) -> ExpressionGuidance:
        """Return bounded candidates and measured style constraints."""
        ranked: list[ExpressionCandidate] = []
        strong_context = (
            situation.confidence >= _STRONG_CONTEXT_CONFIDENCE
            and situation.intent in {"joke", "sarcasm", "hype", "comfort", "media_reaction"}
        )
        if strong_context:
            for profile in profiles:
                if not profile.available or profile.family not in situation.families:
                    continue
                repetition_penalty = 0.3 if profile.value in snapshot.recent_emoji else 0.0
                score = profile.confidence * (0.9 + min(style.emoji_rate, 0.1)) - repetition_penalty
                if score >= _MIN_CANDIDATE_SCORE:
                    ranked.append(ExpressionCandidate(profile, score, "situation_match"))
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ExpressionGuidance(
            situation=situation,
            candidates=tuple(ranked[:3]),
            avoid_emoji=snapshot.recent_emoji,
            avoid_dash=style.em_dash_rate < _RARE_DASH_RATE or bool(snapshot.dash_ages),
            avoid_openings=snapshot.recent_openings[-2:],
            allow_repeat_override=(
                strong_context and situation.confidence >= _REPEAT_OVERRIDE_CONFIDENCE
            ),
            target_words=style.median_words,
        )
