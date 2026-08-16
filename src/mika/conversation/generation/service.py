"""Primary/fallback provider execution for one structured candidate."""

from __future__ import annotations

from dataclasses import dataclass

from mika.ai.llm.chat.pipeline import run_turn
from mika.ai.llm.providers.base import ChatProvider, Message
from mika.ai.llm.tools.registry import ToolRegistry
from mika.ai.llm.turn import MikaTurn
from mika.conversation.generation.parser import TurnParser
from mika.conversation.generation.prompt import PromptComposer
from mika.conversation.trace_service import TurnTraceService


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    """Provider-independent generation settings."""

    primary_model: str
    fallback_model: str
    temperature: float
    max_tokens: int


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """All evidence needed for one provider turn."""

    system: str
    history: tuple[Message, ...]
    user_text: str
    images: tuple[str, ...] = ()
    search_query: str = ""
    tool_names: tuple[str, ...] = ()
    decision_text: str = ""


class GenerationService:
    """Generate through the primary provider with one configured fallback."""

    def __init__(
        self,
        primary: ChatProvider,
        fallback: ChatProvider | None,
        registry: ToolRegistry,
        config: GenerationConfig,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._registry = registry
        self._config = config
        self._parser = TurnParser()
        self._prompt = PromptComposer()

    async def generate(
        self, request: GenerationRequest, *, trace: TurnTraceService | None = None
    ) -> MikaTurn:
        """Return one parsed candidate without leaking provider output to traces."""
        provider, model, outcome = self._primary, self._config.primary_model, "primary"
        try:
            raw = await self._run(provider, model, request, use_tools=bool(request.tool_names))
        except Exception:
            if self._fallback is None:
                raw = ""
                outcome = "failed"
            else:
                provider, model, outcome = self._fallback, self._config.fallback_model, "fallback"
                try:
                    raw = await self._run(provider, model, request, use_tools=False)
                except Exception:
                    raw = ""
                    outcome = "failed"
        if trace is not None:
            trace.record("generation", outcome, details={"provider": outcome})
        decision_text = request.decision_text or request.user_text
        turn = self._parser.parse(raw, user_input=decision_text)
        if turn.parse_status == "json":
            return turn
        retry = GenerationRequest(
            request.system,
            request.history,
            request.user_text + "\nReturn one valid mika_turn.v2 JSON object only.",
            request.images,
            request.search_query,
            decision_text=request.decision_text,
        )
        try:
            repaired = await self._run(provider, model, retry, use_tools=False)
        except Exception:
            return turn
        candidate = self._parser.parse(repaired, user_input=decision_text)
        return candidate if candidate.parse_status == "json" else turn

    async def _run(
        self, provider: ChatProvider, model: str, request: GenerationRequest, *, use_tools: bool
    ) -> str:
        return await run_turn(
            provider,
            system=request.system,
            history=list(request.history),
            user_text=self._prompt.structured(request.user_text),
            registry=self._registry,
            use_tools=use_tools,
            tool_names=request.tool_names,
            model=model,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            require_json=True,
            images=list(request.images) or None,
            search_query=request.search_query,
        )
