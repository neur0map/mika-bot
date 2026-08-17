"""Conservative social-situation assessment."""

from __future__ import annotations

from mika.conversation.skills.natural_expression.contracts import SocialSituation

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
    energetic = (
        intent in {"joke", "hype", "media_reaction"}
        and normalized >= _ENERGETIC_CONFIDENCE
    )
    mode = "encouraged" if energetic and mentioned else "optional"
    intensity = 0.8 if energetic else 0.45
    return SocialSituation(intent, normalized, mode, families, intensity)
