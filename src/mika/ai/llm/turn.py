"""Structured chat turn result used by Discord event handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_TURN_SCHEMA_VERSION = "mika_turn.v2"
_ALLOWED_REACTIONS = ["👍", "👎", "😭", "💀", "👀", "🤔", "😂", "😬", "❤️", "🔥", "✅"]
_TURN_INTENTS = [
    "chat",
    "joke",
    "sarcasm",
    "flirt",
    "hype",
    "comfort",
    "question",
    "criticism",
    "media_reaction",
    "serious",
    "silence",
]
_MEDIA_TYPES = ["none", "gif", "sticker", "clip"]


@dataclass(frozen=True, slots=True)
class MediaChoice:
    """Optional expressive media choice for a reply."""

    kind: str = "none"
    query: str | None = None


@dataclass(frozen=True, slots=True)
class MikaTurn:
    """One bot decision: text, optional reaction, optional media."""

    reply: str
    reactions: tuple[str, ...] = ()
    media: MediaChoice = MediaChoice()
    intent: str = "chat"
    confidence: float = 0.5
    schema_version: str = _TURN_SCHEMA_VERSION
    parse_status: str = "json"
    raw: str = ""

    @property
    def is_silent(self) -> bool:
        """Whether this turn intentionally leaves the conversation alone."""
        return (
            self.intent == "silence"
            and not self.reply
            and not self.reactions
            and self.media.kind == "none"
        )


def mika_turn_response_format() -> dict[str, Any]:
    """Return the strict OpenAI-compatible schema for a Mika social turn."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "mika_turn_v2",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "schema_version",
                    "reply",
                    "reactions",
                    "media",
                    "intent",
                    "confidence",
                ],
                "properties": {
                    "schema_version": {"type": "string", "const": _TURN_SCHEMA_VERSION},
                    "reply": {"type": "string", "maxLength": 500},
                    "reactions": {
                        "type": "array",
                        "items": {"type": "string", "enum": _ALLOWED_REACTIONS},
                        "maxItems": 2,
                    },
                    "media": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["type", "query"],
                        "properties": {
                            "type": {"type": "string", "enum": _MEDIA_TYPES},
                            "query": {"type": ["string", "null"], "maxLength": 80},
                        },
                    },
                    "intent": {"type": "string", "enum": _TURN_INTENTS},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
    }
