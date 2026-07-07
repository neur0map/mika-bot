"""High-level LLM client: turns a user message into a reply, with memory + tools."""

from __future__ import annotations

import json
import re
from typing import Any

from mika.ai.learning.reflection import last_reflection
from mika.ai.llm.chat.pipeline import run_turn
from mika.ai.llm.chat.prompt import build_system_prompt
from mika.ai.llm.memory.honcho import HonchoMemory
from mika.ai.llm.memory.store import LocalMemory
from mika.ai.llm.providers.base import ChatProvider, Message
from mika.ai.llm.providers.openai_compatible import OpenAICompatibleProvider
from mika.ai.llm.tools.registry import ToolRegistry
from mika.ai.llm.tools.web_search import web_search_tool
from mika.ai.llm.turn import MediaChoice, MikaTurn
from mika.core.config import get_settings
from mika.core.logging import get_logger

logger = get_logger(__name__)

_BUSY_REPLY = "brain snagged. give me a second and try again."
_ALLOWED_REACTIONS = {"👍", "👎", "😭", "💀", "👀", "🤔", "😂", "😬", "❤️", "🔥", "✅"}
_MEDIA_TYPES = {"none", "gif", "sticker", "clip"}
_TURN_SCHEMA_VERSION = "mika_turn.v2"
_AVOID_PHRASE_LIMIT = 4
_AVOID_PHRASE_CHARS = 180
_TURN_INTENTS = {
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
}


class LLMClient:
    """Orchestrates memory, persona, and the provider to answer a message."""

    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._provider: ChatProvider = OpenAICompatibleProvider(
            base_url=settings.llm.base_url, api_key=settings.llm.api_key
        )
        self._fallback: ChatProvider | None = (
            OpenAICompatibleProvider(
                base_url=settings.llm.fallback_base_url, api_key=settings.llm.fallback_api_key
            )
            if settings.llm.has_fallback
            else None
        )
        self._local = LocalMemory()
        self._honcho = HonchoMemory() if settings.memory.honcho_enabled else None
        self._tools = ToolRegistry()
        if settings.tools.web_search_enabled:
            self._tools.register(web_search_tool())

    async def startup(self) -> None:
        """One-time setup (provision Honcho if enabled)."""
        if self._honcho is not None:
            await self._honcho.ensure()

    async def reply(
        self,
        *,
        channel_id: str,
        author_id: str,
        author_name: str,
        text: str,
        media_context: str = "",
    ) -> MikaTurn:
        """Produce one structured reply decision and persist the exchange."""
        history = await self._build_history(channel_id)
        user_input = self._compose_user_input(text, media_context)
        generation_input = self._compose_generation_input(user_input, history)
        recall = await self._honcho.recall(user_input) if self._honcho is not None else ""
        reflection, _ = await last_reflection()
        system = build_system_prompt(self._memory_context(recall, reflection))
        raw = await self._generate(system, history, f"{author_name}: {generation_input}")
        turn = self._parse_turn(raw)
        await self._persist(channel_id, author_id, author_name, user_input, turn.reply)
        return turn

    def _compose_user_input(self, text: str, media_context: str = "") -> str:
        clean_text = text.strip()
        clean_media = media_context.strip()
        if clean_text and clean_media:
            return f"{clean_text}\n{clean_media}"
        return clean_text or clean_media or "[media/message with no text]"

    def _compose_generation_input(self, user_input: str, history: list[Message]) -> str:
        avoid = self._recent_assistant_phrases(history)
        if not avoid:
            return user_input
        lines = "\n".join(f"- {phrase}" for phrase in avoid)
        return (
            f"{user_input}\n\n"
            "[recent assistant wording to avoid repeating; keep the same personality "
            f"but vary rhythm, joke shape, and phrasing.]\n{lines}"
        )

    def _memory_context(self, recall: str, reflection: str | None) -> str:
        sections: list[str] = []
        if recall.strip():
            sections.append(recall.strip())
        if reflection and reflection.strip():
            sections.append("Recent self-reflection lessons:\n" + reflection.strip())
        return "\n\n".join(sections)

    def _recent_assistant_phrases(self, history: list[Message]) -> list[str]:
        phrases: list[str] = []
        for message in reversed(history):
            if message.get("role") != "assistant":
                continue
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            phrases.append(content[:_AVOID_PHRASE_CHARS])
            if len(phrases) == _AVOID_PHRASE_LIMIT:
                break
        return phrases

    async def _build_history(self, channel_id: str) -> list[Message]:
        rows = await self._local.recent(channel_id)
        history: list[Message] = []
        for role, author, content in rows:
            if role == "user":
                history.append({"role": "user", "content": f"{author}: {content}"})
            else:
                history.append({"role": "assistant", "content": content})
        return history

    async def _generate(self, system: str, history: list[Message], user_text: str) -> str:
        settings = self._settings
        structured_user_text = self._structured_instruction(user_text)
        try:
            return await run_turn(
                self._provider,
                system=system,
                history=history,
                user_text=structured_user_text,
                registry=self._tools,
                use_tools=bool(self._tools),
                model=settings.llm.model,
                temperature=settings.llm.temperature,
                max_tokens=settings.llm.max_tokens,
            )
        except Exception as primary_error:
            logger.warning("primary provider failed: %s", primary_error)
        if self._fallback is None:
            return _BUSY_REPLY
        try:
            return await run_turn(
                self._fallback,
                system=system,
                history=history,
                user_text=structured_user_text,
                registry=self._tools,
                use_tools=False,
                model=settings.llm.fallback_model,
                temperature=settings.llm.temperature,
                max_tokens=settings.llm.max_tokens,
            )
        except Exception as fallback_error:
            logger.error("fallback provider failed: %s", fallback_error)
            return _BUSY_REPLY

    def _structured_instruction(self, user_text: str) -> str:
        return (
            f"{user_text}\n\n"
            "Return strict JSON only with keys: schema_version, reply, reactions, "
            "media, intent, confidence. schema_version is 'mika_turn.v2'. reply is "
            "the Discord message text. reactions is 0-1 emoji from "
            "[👍,👎,😭,💀,👀,🤔,😂,😬,❤️,🔥,✅]. media is "
            "{type:'none'|'gif'|'sticker'|'clip', query:null|string}. intent is one of "
            "chat, joke, sarcasm, flirt, hype, comfort, question, criticism, "
            "media_reaction, serious. confidence is a number from 0 to 1 for the social "
            "read, not factual certainty. Use reactions/GIFs only when a real Discord user "
            "would. For incoming media, decide if it is probably a joke, sarcasm, flirting, "
            "hype, confusion, or a serious share; do not describe or caption the GIF/image "
            "unless asked. Choose between text, one reaction, matching with a GIF, or "
            "staying dry. No explanations of this JSON."
        )

    def _parse_turn(self, raw: str) -> MikaTurn:
        text = raw.strip()
        candidate = self._extract_json_object(text) or text
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            reply = self._extract_labeled_reply(text) or self._clean_reply_text(text)
            return MikaTurn(reply=reply or _BUSY_REPLY, raw=raw)
        reply = str(data.get("reply") or data.get("message") or "").strip()
        reply = self._clean_reply_text(reply) or _BUSY_REPLY
        raw_reactions = data.get("reactions") if isinstance(data.get("reactions"), list) else []
        reactions = tuple(str(item) for item in raw_reactions if str(item) in _ALLOWED_REACTIONS)[
            :1
        ]
        raw_media = data.get("media") if isinstance(data.get("media"), dict) else {}
        media_type = str(raw_media.get("type") or "none").lower()
        if media_type not in _MEDIA_TYPES:
            media_type = "none"
        query_value = raw_media.get("query")
        query = str(query_value).strip()[:80] if query_value else None
        intent = str(data.get("intent") or "chat").strip().lower()
        if intent not in _TURN_INTENTS:
            intent = "chat"
        confidence = self._bounded_confidence(data.get("confidence"))
        schema_version = str(data.get("schema_version") or _TURN_SCHEMA_VERSION).strip()
        return MikaTurn(
            reply=reply[:1900],
            reactions=reactions,
            media=MediaChoice(media_type, query),
            intent=intent,
            confidence=confidence,
            schema_version=schema_version or _TURN_SCHEMA_VERSION,
            raw=raw,
        )

    def _bounded_confidence(self, value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, number))

    def _extract_json_object(self, text: str) -> str | None:
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        in_string = False
        escaped = False
        for index, char in enumerate(text[start:], start=start):
            if escaped:
                escaped = False
                continue
            if char == "\\" and in_string:
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        return None

    def _extract_labeled_reply(self, text: str) -> str | None:
        match = re.search(
            r"(?:^|\s)reply\s*:\s*(?P<reply>.*?)(?:\s+(?:media|reactions?)\s*:|$)",
            text,
            flags=re.I | re.S,
        )
        if not match:
            return None
        return self._clean_reply_text(match.group("reply"))

    def _clean_reply_text(self, text: str) -> str:
        cleaned = text.strip()
        cleaned = re.sub(r"\s+(?:media|reactions?)\s*:\s*[^\n]+$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"^reply\s*:\s*", "", cleaned, flags=re.I)
        return re.sub(r"\s{2,}", " ", cleaned).strip()

    async def summarize(self, instruction: str, content: str, *, model: str | None = None) -> str:
        """One-shot completion with no memory or tools (used by self-reflection)."""
        messages: list[Message] = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": content},
        ]
        try:
            result = await self._provider.complete(
                messages, model=model or self._settings.llm.model, max_tokens=600
            )
            return result.content or ""
        except Exception as error:
            logger.warning("summarize failed: %s", error)
            return ""

    async def _persist(
        self, channel_id: str, author_id: str, author_name: str, text: str, answer: str
    ) -> None:
        await self._local.remember(
            channel_id=channel_id,
            author_id=author_id,
            author_name=author_name,
            role="user",
            content=text,
        )
        await self._local.remember(
            channel_id=channel_id,
            author_id="bot",
            author_name=self._settings.persona.name,
            role="assistant",
            content=answer,
        )
        if self._honcho is not None:
            await self._honcho.remember_user(
                discord_id=author_id, author_name=author_name, content=text
            )
            await self._honcho.remember_bot(answer)
