"""Defensive parsing and deterministic bounds for social turn candidates."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any

from mika.ai.llm.turn import MediaChoice, MikaTurn

_BUSY_REPLY = "brain snagged. give me a second and try again."
_ALLOWED_REACTIONS = {"👍", "👎", "😭", "💀", "👀", "🤔", "😂", "😬", "❤️", "🔥", "✅"}
_MEDIA_TYPES = {"none", "gif", "sticker", "clip"}
_MEDIA_INTENTS = {"media_reaction", "hype", "joke", "flirt", "sarcasm"}
_MEDIA_CONFIDENCE = 0.6
_INTENTS = {
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
}
_SHORT_INTENTS = {"chat", "joke", "sarcasm", "flirt", "hype", "criticism", "media_reaction"}
_MEDIA_REQUEST = re.compile(
    r"\b(?:send|post|drop|find|get|use|give|match).*\b(gif|sticker|clip)\b|"
    r"\b(gif|sticker|clip)\s+me\b",
    re.I,
)


class TurnParser:
    """Parse imperfect model output into one safe candidate turn."""

    def parse(self, raw: str, *, user_input: str = "") -> MikaTurn:
        """Parse, normalize, and bound one provider response."""
        text = raw.strip()
        candidate = self.extract_json(text) or text
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            labeled = self._labeled_reply(text)
            reply = labeled or self._clean_reply(text) or _BUSY_REPLY
            return MikaTurn(reply=reply, parse_status="labeled" if labeled else "fallback", raw=raw)
        turn = self._from_mapping(data, raw)
        turn = self._requested_media(turn, user_input)
        turn = self._eligible_media(turn, user_input)
        return MikaTurn(
            reply=self.limit_reply(turn.reply, turn.intent),
            reactions=turn.reactions,
            media=turn.media,
            intent=turn.intent,
            confidence=turn.confidence,
            schema_version=turn.schema_version,
            parse_status=turn.parse_status,
            raw=turn.raw,
        )

    def _from_mapping(self, data: Any, raw: str) -> MikaTurn:
        if not isinstance(data, dict):
            return MikaTurn(reply=_BUSY_REPLY, parse_status="fallback", raw=raw)
        reply = self._clean_reply(str(data.get("reply") or data.get("message") or ""))
        reactions = tuple(
            str(item)
            for item in self._reaction_list(data.get("reactions"))
            if str(item) in _ALLOWED_REACTIONS
        )[:1]
        media_value = data.get("media")
        raw_media: dict[str, Any] = media_value if isinstance(media_value, dict) else {}
        media_type = str(raw_media.get("type") or "none").lower()
        media_type = media_type if media_type in _MEDIA_TYPES else "none"
        query_value = raw_media.get("query")
        query = str(query_value).strip()[:80] if query_value else None
        intent = str(data.get("intent") or "chat").strip().lower()
        intent = intent if intent in _INTENTS else "chat"
        silent = intent == "silence" and not reply and not reactions and media_type == "none"
        if not reply and not reactions and media_type == "none" and not silent:
            reply = _BUSY_REPLY
        return MikaTurn(
            reply=reply[:1900],
            reactions=reactions,
            media=MediaChoice(media_type, query),
            intent=intent,
            confidence=self._confidence(data.get("confidence")),
            schema_version=str(data.get("schema_version") or "mika_turn.v2"),
            raw=raw,
        )

    def extract_json(self, text: str) -> str | None:
        """Return the first balanced JSON object outside quoted braces."""
        start = text.find("{")
        if start < 0:
            return None
        depth, in_string, escaped = 0, False, False
        for index, char in enumerate(text[start:], start=start):
            if escaped:
                escaped = False
            elif char == "\\" and in_string:
                escaped = True
            elif char == '"':
                in_string = not in_string
            elif not in_string and char == "{":
                depth += 1
            elif not in_string and char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        return None

    def limit_reply(self, reply: str, intent: str) -> str:
        """Bound social turns more tightly than substantive answers."""
        limit = 180 if intent in _SHORT_INTENTS else 500
        if len(reply) <= limit:
            return reply
        clipped = reply[: limit - 1].rstrip()
        boundary = max(clipped.rfind(". "), clipped.rfind("! "), clipped.rfind("? "))
        if boundary >= limit // 3:
            return clipped[: boundary + 1].rstrip()
        word = clipped.rfind(" ")
        return (clipped[:word] if word > 0 else clipped) + "…"

    @staticmethod
    def _reaction_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        return [value.strip()] if isinstance(value, str) and value.strip() else []

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.5

    def _labeled_reply(self, text: str) -> str | None:
        match = re.search(
            r"(?:^|\s)reply\s*:\s*(?P<reply>.*?)(?:\s+(?:media|reactions?)\s*:|$)",
            text,
            flags=re.I | re.S,
        )
        return self._clean_reply(match.group("reply")) if match else None

    @staticmethod
    def _clean_reply(text: str) -> str:
        cleaned = re.sub(r"\s+(?:media|reactions?)\s*:\s*[^\n]+$", "", text.strip(), flags=re.I)
        cleaned = re.sub(r"^reply\s*:\s*", "", cleaned, flags=re.I)
        return re.sub(r"\s{2,}", " ", cleaned).strip()

    def _requested_media(self, turn: MikaTurn, user_input: str) -> MikaTurn:
        if turn.media.kind != "none" or not _MEDIA_REQUEST.search(user_input):
            return turn
        kind_match = re.search(r"\b(gif|sticker|clip)\b", user_input, re.I)
        kind = kind_match.group(1).lower() if kind_match else "gif"
        query = re.sub(
            r"\b(?:send|post|drop|find|get|use|give|a|the|gif|sticker|clip|of)\b",
            " ",
            user_input,
            flags=re.I,
        )
        query = re.sub(r"[^\w\s'-]", " ", query)
        query = re.sub(r"\s+", " ", query).strip()[:80]
        return (
            replace(turn, media=MediaChoice(kind, query), intent="media_reaction")
            if query
            else turn
        )

    @staticmethod
    def _eligible_media(turn: MikaTurn, user_input: str) -> MikaTurn:
        if turn.media.kind == "none" or _MEDIA_REQUEST.search(user_input):
            return turn
        if turn.intent in _MEDIA_INTENTS and turn.confidence >= _MEDIA_CONFIDENCE:
            return turn
        return replace(turn, media=MediaChoice())
