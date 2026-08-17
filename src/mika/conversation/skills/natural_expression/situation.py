"""Conservative social-situation assessment."""

from __future__ import annotations

import re

from mika.conversation.skills.natural_expression.contracts import EmojiMode, SocialSituation

_FAMILIES: dict[str, tuple[str, ...]] = {
    "joke": ("amusement",),
    "sarcasm": ("skepticism", "amusement"),
    "flirt": ("warmth",),
    "hype": ("celebration",),
    "comfort": ("support", "warmth"),
    "criticism": ("awkwardness",),
    "media_reaction": ("amusement", "curiosity"),
    "question": ("curiosity",),
    "chat": ("warmth",),
}
_SERIOUS = {"serious", "silence"}
_MIN_EXPRESSION_CONFIDENCE = 0.45
_ENERGETIC_CONFIDENCE = 0.8
_INTENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("sarcasm", re.compile(r"\b(?:great,? another|love that|exactly what i wanted)\b", re.I)),
    (
        "hype",
        re.compile(r"\b(?:we (?:actually )?won|got the job|shipped it|we are so back)\b", re.I),
    ),
    ("comfort", re.compile(r"\b(?:rough|feeling alone|still failed|bad day)\b", re.I)),
    ("flirt", re.compile(r"\b(?:cute|blush|smooth talker)\b", re.I)),
    ("joke", re.compile(r"\b(?:lmao|lol|handcrafted bug|speedrun|meme)\b", re.I)),
)


def infer_intent(text: str) -> str:
    """Return a high-precision social intent hint before generation."""
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(text):
            return intent
    return "chat"


def assess_situation(
    text: str,
    intent: str,
    confidence: float,
    mentioned: bool,
) -> SocialSituation:
    """Map existing turn signals to bounded expression eligibility."""
    normalized = max(0.0, min(1.0, confidence))
    if intent in _SERIOUS or normalized < _MIN_EXPRESSION_CONFIDENCE:
        return SocialSituation(intent, normalized, "avoid")
    families = _FAMILIES.get(intent, ())
    if not families:
        return SocialSituation(intent, normalized, "avoid")
    energetic = intent in {"joke", "hype", "media_reaction"} and normalized >= _ENERGETIC_CONFIDENCE
    mode: EmojiMode = "encouraged" if energetic and mentioned else "optional"
    intensity = 0.8 if energetic else 0.45
    return SocialSituation(intent, normalized, mode, families, intensity)
