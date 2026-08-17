"""Curated semantic families for standard Unicode emoji."""

from __future__ import annotations

from mika.conversation.skills.natural_expression.contracts import EmojiProfile, SocialSituation

_CATALOG: dict[str, tuple[EmojiProfile, ...]] = {
    "amusement": (
        EmojiProfile("😂", "amusement", "genuine laughter", 0.82),
        EmojiProfile("😭", "amusement", "overwhelmed laughter", 0.76),
        EmojiProfile("💀", "amusement", "deadpan extreme amusement", 0.74),
    ),
    "warmth": (
        EmojiProfile("🙂", "warmth", "quiet friendliness", 0.72),
        EmojiProfile("🫶", "warmth", "warm appreciation", 0.74),
    ),
    "support": (
        EmojiProfile("❤️", "support", "care and support", 0.78),
        EmojiProfile("🫂", "support", "comfort", 0.76),
    ),
    "celebration": (
        EmojiProfile("🔥", "celebration", "strong approval or hype", 0.8),
        EmojiProfile("🎉", "celebration", "celebration", 0.82),
    ),
    "skepticism": (
        EmojiProfile("🤨", "skepticism", "playful disbelief", 0.75),
        EmojiProfile("👀", "skepticism", "watching with interest", 0.7),
    ),
    "awkwardness": (EmojiProfile("😬", "awkwardness", "awkward tension", 0.78),),
    "sadness": (EmojiProfile("😔", "sadness", "quiet sadness", 0.72),),
    "agreement": (
        EmojiProfile("👍", "agreement", "simple agreement", 0.78, placement="reaction"),
        EmojiProfile("✅", "agreement", "clear confirmation", 0.78, placement="reaction"),
    ),
    "curiosity": (
        EmojiProfile("🤔", "curiosity", "thinking or uncertainty", 0.72),
        EmojiProfile("👀", "curiosity", "interested attention", 0.7),
    ),
}


def unicode_candidates(situation: SocialSituation) -> tuple[EmojiProfile, ...]:
    """Return a bounded candidate set without implying that one must be used."""
    if situation.emoji_mode == "avoid":
        return ()
    candidates: list[EmojiProfile] = []
    for family in situation.families[:2]:
        candidates.extend(_CATALOG.get(family, ())[:3])
    return tuple(candidates[:4])
