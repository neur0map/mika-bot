"""High-level LLM client: turns a user message into a reply, with memory + tools."""

from __future__ import annotations

import json
import re

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
        recall = await self._honcho.recall(user_input) if self._honcho is not None else ""
        system = build_system_prompt(recall)
        raw = await self._generate(system, history, f"{author_name}: {user_input}")
        turn = self._parse_turn(raw)
        await self._persist(channel_id, author_id, author_name, user_input, turn.reply)
        return turn

    def _compose_user_input(self, text: str, media_context: str = "") -> str:
        clean_text = text.strip()
        clean_media = media_context.strip()
        if clean_text and clean_media:
            return f"{clean_text}\n{clean_media}"
        return clean_text or clean_media or "[media/message with no text]"

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
            "Return strict JSON only with keys: reply, reactions, media. "
            "reply is the Discord message text. reactions is 0-1 emoji from "
            "[👍,👎,😭,💀,👀,🤔,😂,😬,❤️,🔥,✅]. media is "
            "{type:'none'|'gif'|'sticker'|'clip', query:null|string}. "
            "Use reactions/GIFs only when a real Discord user would. For incoming media, "
            "decide if it is probably a joke, sarcasm, flirting, hype, confusion, or a serious "
            "share; do not describe or caption the GIF/image unless asked. Choose between text, "
            "one reaction, matching with a GIF, or staying dry. No explanations of this JSON."
        )

    def _parse_turn(self, raw: str) -> MikaTurn:
        text = raw.strip()
        candidate = text
        if not candidate.startswith("{"):
            match = re.search(r"\{.*\}", candidate, flags=re.S)
            candidate = match.group(0) if match else candidate
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
        return MikaTurn(
            reply=reply[:1900], reactions=reactions, media=MediaChoice(media_type, query), raw=raw
        )

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
