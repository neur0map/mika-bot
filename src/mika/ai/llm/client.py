"""High-level LLM client: turns a user message into a reply, with memory + tools."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING

from mika.ai.learning.reflection import last_reflection
from mika.ai.llm.chat.prompt import build_system_prompt
from mika.ai.llm.memory.honcho import HonchoMemory
from mika.ai.llm.memory.store import LocalMemory
from mika.ai.llm.providers.base import ChatProvider, Message
from mika.ai.llm.providers.factory import build_fallback_provider, build_provider
from mika.ai.llm.tools.registry import ToolRegistry
from mika.ai.llm.turn import MediaChoice, MikaTurn
from mika.conversation.context import SelectedContext
from mika.conversation.context.retrieval import merge_memory_text
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.generation import (
    GenerationConfig,
    GenerationRequest,
    GenerationService,
    PromptComposer,
    TurnParser,
)
from mika.conversation.media import TemporalMediaSampler, media_context
from mika.conversation.participation import ParticipationDecision
from mika.conversation.skills.natural_expression import NaturalExpressionSkill, infer_intent
from mika.conversation.skills.natural_expression.guild_catalog import (
    GuildEmojiCatalog,
    GuildEmojiDescriptor,
)
from mika.conversation.skills.natural_expression.human_style import load_archive_profiles
from mika.conversation.skills.natural_expression.visual_profile import VisualProfiler
from mika.conversation.tools import ToolPlan
from mika.conversation.tools.abilities.web_search import web_search_tool
from mika.core.config import get_settings
from mika.core.logging import get_logger
from mika.persistence.conversations.managed_expression_profiles import ManagedExpressionProfiles

if TYPE_CHECKING:
    from mika.conversation.trace_service import TurnTraceService

logger = get_logger(__name__)

_MEDIA_OK_INTENTS = {"media_reaction", "hype", "joke", "flirt", "sarcasm"}
_MEDIA_INTENT_CONFIDENCE = 0.6
_MEDIA_REQUEST_RE = re.compile(
    r"\b(?:send|post|drop|find|get|use|give|match).*\b(gif|sticker|clip)\b|"
    r"\b(gif|sticker|clip)\s+me\b",
    re.I,
)
_MEDIA_NOISE_RE = re.compile(
    r"\b(?:send|post|drop|find|get|use|give|match|a|an|the|gif|sticker|clip|"
    r"of|for|please|pls)\b",
    re.I,
)
_CURRENT_FACT_RE = re.compile(
    r"\b(?:today(?:'s)?|current|latest|news|weather|forecast|score|scores|"
    r"standings|price|prices|stock|release date|who won|when did)\b",
    re.I,
)
_SOCIAL_OR_JOKE_RE = re.compile(
    r"\b(?:lol|lmao|lmfao|joke|kidding|jk|meme|bro|bruh|😭|💀|😂)\b",
    re.I,
)
_PROMPT = PromptComposer()
_TURN_PARSER = TurnParser()


class LLMClient:
    """Orchestrates memory, persona, and the provider to answer a message."""

    def __init__(self, memory: LocalMemory | None = None) -> None:
        settings = get_settings()
        self._settings = settings
        self._provider: ChatProvider = build_provider(settings.llm, data_dir=settings.data_dir)
        self._fallback: ChatProvider | None = build_fallback_provider(
            settings.llm, data_dir=settings.data_dir
        )
        self._local = memory or LocalMemory()
        self._honcho = HonchoMemory() if settings.memory.honcho_enabled else None
        self._tools = ToolRegistry()
        self._media = TemporalMediaSampler()
        self._style_profiles = load_archive_profiles(settings.shared_archive_path)
        self._expression = NaturalExpressionSkill(self._style_profiles.server)
        self._emoji_catalog = GuildEmojiCatalog()
        self._visual_profiler = VisualProfiler()
        self._expression_profiles = ManagedExpressionProfiles()
        if settings.tools.web_search_enabled:
            self._tools.register(web_search_tool())
        self._generation = GenerationService(
            self._provider,
            self._fallback,
            self._tools,
            GenerationConfig(
                settings.llm.model,
                settings.llm.fallback_model,
                settings.llm.temperature,
                settings.llm.max_tokens,
            ),
        )

    async def startup(self) -> None:
        """One-time setup (provision Honcho if enabled)."""
        if self._honcho is not None:
            await self._honcho.ensure()

    async def shutdown(self) -> None:
        """Release providers that own a subprocess (Codex/ACP)."""
        for provider in (self._provider, self._fallback):
            closer = getattr(provider, "aclose", None)
            if closer is not None:
                await closer()

    async def sync_guild_emojis(
        self, guild_id: str, descriptors: list[GuildEmojiDescriptor]
    ) -> None:
        """Refresh rename-safe custom emoji profiles from Discord metadata."""
        self._emoji_catalog.sync(guild_id, descriptors)
        for descriptor in descriptors:
            evidence = self._visual_profiler.describe(descriptor.name, animated=descriptor.animated)
            await self._expression_profiles.upsert(
                guild_id,
                descriptor.emoji_id,
                descriptor.name,
                descriptor.animated,
                descriptor.available,
                evidence.description,
                evidence.family,
                evidence.confidence,
            )
        for stored in await self._expression_profiles.list(guild_id):
            try:
                self._emoji_catalog.set_description(
                    guild_id,
                    stored.emoji_id,
                    stored.description,
                    stored.family,
                    stored.confidence,
                )
            except KeyError:
                continue

    async def reply(
        self,
        *,
        channel_id: str,
        author_id: str,
        author_name: str,
        text: str,
        media_context: str = "",
        media_urls: list[str] | None = None,
        trace: TurnTraceService | None = None,
    ) -> MikaTurn:
        """Produce one structured reply decision and persist the exchange.

        `media_urls` are image/GIF links from the message; providers that support
        vision see the picture itself, not just the `media_context` label.
        """
        if trace is None:
            history = await self._build_history(channel_id)
        else:
            with trace.measure("retrieval"):
                history = await self._build_history(channel_id)
        user_input = self._compose_user_input(text, media_context)
        intent_hint = infer_intent(user_input)
        guidance = self._expression.guide(
            channel_id,
            user_input,
            intent_hint,
            0.9 if intent_hint != "chat" else 0.7,
            mentioned=True,
            channel_style=self._style_profiles.channels.get(channel_id),
            person_style=self._style_profiles.people.get(author_id),
        )
        generation_input = self._compose_generation_input(user_input, history, guidance.render())
        recall = await self._honcho.recall(user_input) if self._honcho is not None else ""
        reflection, _ = await last_reflection()
        system = build_system_prompt(self._memory_context(recall, reflection))
        use_tools = self._should_use_tools(user_input)
        if trace is not None:
            trace.record("context", "ready", details={"history_count": len(history)})
            trace.record("tools", "eligible" if use_tools else "skipped")

        turn = await self._generation.generate(
            GenerationRequest(
                system=system,
                history=tuple(history),
                user_text=f"{author_name}: {generation_input}",
                images=tuple(media_urls or ()),
                search_query=text,
                tool_names=("web_search",) if use_tools else (),
                decision_text=user_input,
            ),
            trace=trace,
        )
        final_guidance = self._expression.guide(
            channel_id,
            user_input,
            turn.intent,
            turn.confidence,
            mentioned=True,
            channel_style=self._style_profiles.channels.get(channel_id),
            person_style=self._style_profiles.people.get(author_id),
        )
        turn = replace(turn, reply=self._expression.validate(turn.reply, final_guidance))
        await self._persist(channel_id, author_id, author_name, user_input, turn.reply)
        return turn

    async def generate(
        self,
        envelope: ConversationEnvelope,
        context: SelectedContext,
        participation: ParticipationDecision,
        tools: ToolPlan,
    ) -> MikaTurn:
        """Generate from already-selected engine context without persisting twice."""
        history: list[Message] = [
            {
                "role": "user" if item.role == "user" else "assistant",
                "content": f"{item.author_name}: {item.content}"
                if item.role == "user"
                else item.content,
            }
            for item in context.history
        ]
        user_input = self._compose_user_input(envelope.text, media_context(envelope.visual_inputs))
        channel_style = self._style_profiles.channels.get(envelope.channel_id)
        person_style = self._style_profiles.people.get(envelope.author_id)
        profiles = self._emoji_catalog.profiles(envelope.guild_id)
        intent_hint = infer_intent(user_input)
        guidance = self._expression.guide(
            envelope.channel_id,
            user_input,
            intent_hint,
            0.9 if intent_hint != "chat" else 0.7,
            envelope.mentioned,
            profiles=profiles,
            channel_style=channel_style,
            person_style=person_style,
        )
        generation_input = self._compose_generation_input(user_input, history, guidance.render())
        recall = await self._honcho.recall(user_input) if self._honcho is not None else ""
        reflection, _ = await last_reflection()
        memory_context = merge_memory_text(context.memory, recall)
        system = build_system_prompt(self._memory_context(memory_context, reflection))
        turn = await self._generation.generate(
            GenerationRequest(
                system=system,
                history=tuple(history),
                user_text=f"{envelope.author_name}: {generation_input}",
                images=await self._media.prepare(envelope.visual_inputs),
                search_query=envelope.text,
                tool_names=tools.names,
                decision_text=user_input,
            )
        )
        final_guidance = self._expression.guide(
            envelope.channel_id,
            user_input,
            turn.intent,
            turn.confidence,
            envelope.mentioned,
            profiles=profiles,
            channel_style=channel_style,
            person_style=person_style,
        )
        turn = replace(turn, reply=self._expression.validate(turn.reply, final_guidance))
        return self._gate_media_choice(self._force_requested_media(turn, user_input), user_input)

    def _compose_user_input(self, text: str, media_context: str = "") -> str:
        return _PROMPT.user_input(text, media_context)

    def _compose_generation_input(
        self, user_input: str, history: list[Message], expression_guidance: str = ""
    ) -> str:
        return _PROMPT.generation_input(
            user_input, history, expression_guidance=expression_guidance
        )

    def observe_expression(self, channel_id: str, reply: str, reactions: tuple[str, ...]) -> None:
        """Record style only after Discord rendered the action."""
        self._expression.observe(channel_id, reply, reactions)

    def _memory_context(self, recall: str, reflection: str | None) -> str:
        sections: list[str] = []
        if recall.strip():
            sections.append(recall.strip())
        if reflection and reflection.strip():
            sections.append("Recent self-reflection lessons:\n" + reflection.strip())
        return "\n\n".join(sections)

    def _should_use_tools(self, user_input: str) -> bool:
        if _MEDIA_REQUEST_RE.search(user_input):
            return False
        if _SOCIAL_OR_JOKE_RE.search(user_input):
            return False
        return bool(self._tools) and bool(_CURRENT_FACT_RE.search(user_input))

    def _force_requested_media(self, turn: MikaTurn, user_input: str) -> MikaTurn:
        if turn.media.kind != "none" or not _MEDIA_REQUEST_RE.search(user_input):
            return turn
        kind_match = re.search(r"\b(gif|sticker|clip)\b", user_input, flags=re.I)
        kind = kind_match.group(1).lower() if kind_match else "gif"
        query = self._media_request_query(user_input)
        if not query:
            return turn
        return replace(turn, media=MediaChoice(kind, query), intent="media_reaction")

    def _gate_media_choice(self, turn: MikaTurn, user_input: str) -> MikaTurn:
        if turn.media.kind == "none" or _MEDIA_REQUEST_RE.search(user_input):
            return turn
        if turn.intent in _MEDIA_OK_INTENTS and turn.confidence >= _MEDIA_INTENT_CONFIDENCE:
            return turn
        return replace(turn, media=MediaChoice())

    def _media_request_query(self, user_input: str) -> str:
        first_line = user_input.splitlines()[0]
        first_line = re.sub(r"https?://\S+", " ", first_line)
        cleaned = _MEDIA_NOISE_RE.sub(" ", first_line)
        cleaned = re.sub(r"[^\w\s'-]", " ", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()[:80]

    def _limit_reply(self, reply: str, intent: str) -> str:
        return _TURN_PARSER.limit_reply(reply, intent)

    async def _build_history(self, channel_id: str) -> list[Message]:
        rows = await self._local.recent(channel_id)
        history: list[Message] = []
        for role, author, content in rows:
            if role == "user":
                history.append({"role": "user", "content": f"{author}: {content}"})
            else:
                history.append({"role": "assistant", "content": content})
        return history

    def _parse_turn(self, raw: str) -> MikaTurn:
        return _TURN_PARSER.parse(raw)

    def _extract_json_object(self, text: str) -> str | None:
        return _TURN_PARSER.extract_json(text)

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
