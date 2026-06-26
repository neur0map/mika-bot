"""High-level LLM client: turns a user message into a reply, with memory + tools."""

from __future__ import annotations

from mika.ai.llm.chat.pipeline import run_turn
from mika.ai.llm.chat.prompt import build_system_prompt
from mika.ai.llm.memory.honcho import HonchoMemory
from mika.ai.llm.memory.store import LocalMemory
from mika.ai.llm.providers.base import ChatProvider, Message
from mika.ai.llm.providers.openai_compatible import OpenAICompatibleProvider
from mika.ai.llm.tools.registry import ToolRegistry
from mika.ai.llm.tools.web_search import web_search_tool
from mika.core.config import get_settings
from mika.core.logging import get_logger

logger = get_logger(__name__)

_BUSY_REPLY = "sorry, my brain is having a moment. try again in a bit."


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

    async def reply(self, *, channel_id: str, author_id: str, author_name: str, text: str) -> str:
        """Produce a reply to one user message and persist the exchange."""
        history = await self._build_history(channel_id)
        recall = await self._honcho.recall(text) if self._honcho is not None else ""
        system = build_system_prompt(recall)
        answer = await self._generate(system, history, f"{author_name}: {text}")
        await self._persist(channel_id, author_id, author_name, text, answer)
        return answer

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
        try:
            return await run_turn(
                self._provider,
                system=system,
                history=history,
                user_text=user_text,
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
                user_text=user_text,
                registry=self._tools,
                use_tools=False,
                model=settings.llm.fallback_model,
                temperature=settings.llm.temperature,
                max_tokens=settings.llm.max_tokens,
            )
        except Exception as fallback_error:
            logger.error("fallback provider failed: %s", fallback_error)
            return _BUSY_REPLY

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
