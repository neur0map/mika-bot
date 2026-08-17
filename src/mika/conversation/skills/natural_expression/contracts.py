"""Typed values used by the natural-expression skill."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EmojiMode = Literal["avoid", "optional", "encouraged"]
EmojiKind = Literal["unicode", "guild"]
Placement = Literal["inline", "reaction", "either"]


@dataclass(frozen=True, slots=True)
class SocialSituation:
    """A conservative reading of the current social moment."""

    intent: str
    confidence: float
    emoji_mode: EmojiMode
    families: tuple[str, ...] = ()
    intensity: float = 0.0


@dataclass(frozen=True, slots=True)
class EmojiProfile:
    """Inspectable semantic and eligibility metadata for one emoji."""

    value: str
    family: str
    description: str
    confidence: float
    kind: EmojiKind = "unicode"
    placement: Placement = "either"
    guild_id: str | None = None
    available: bool = True
    safe_public: bool = True
    locked: bool = False


@dataclass(frozen=True, slots=True)
class ExpressionCandidate:
    """One ranked expression option."""

    profile: EmojiProfile
    score: float
    reason: str


@dataclass(frozen=True, slots=True)
class StyleSnapshot:
    """Bounded recent stylistic fingerprints for one channel."""

    recent_emoji: tuple[str, ...] = ()
    recent_families: tuple[str, ...] = ()
    recent_openings: tuple[str, ...] = ()
    dash_ages: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ExpressionGuidance:
    """Compact advice and constraints for one generated turn."""

    situation: SocialSituation
    candidates: tuple[ExpressionCandidate, ...] = ()
    avoid_emoji: tuple[str, ...] = ()
    avoid_families: tuple[str, ...] = ()
    avoid_dash: bool = False
    avoid_openings: tuple[str, ...] = ()
    allow_repeat_override: bool = False
    target_words: int = 5

    def render(self) -> str:
        """Render only the evidence the generator needs for this turn."""
        mode = self.situation.emoji_mode
        lines = [
            f"Natural server style: aim for about {self.target_words} words in one sentence. "
            f"Emoji {mode}; no emoji is the default."
        ]
        if self.candidates:
            choices = ", ".join(
                f"{item.profile.value} ({item.profile.description})" for item in self.candidates
            )
            lines.append(f"Contextually suitable choices: {choices}.")
        avoid: list[str] = []
        if self.avoid_emoji:
            avoid.append("recent emoji " + ", ".join(self.avoid_emoji))
        if self.avoid_families:
            avoid.append("recent emoji families " + ", ".join(self.avoid_families))
        if self.avoid_dash:
            avoid.append("em-dash cadence")
        if self.avoid_openings:
            avoid.append("openings " + ", ".join(self.avoid_openings))
        if avoid:
            lines.append("Avoid repeating " + "; ".join(avoid) + ".")
        lines.append("Use an emoji only when it adds social meaning, not as decoration.")
        return " ".join(lines)
