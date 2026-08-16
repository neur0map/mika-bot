"""Translate staged engine outcomes into blind benchmark observations."""

from __future__ import annotations

from dataclasses import dataclass

from mika.ai.llm.turn import MikaTurn
from mika.conversation.actions import ActionPlan
from mika.conversation.context import SelectedContext
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.engine import TurnGenerator
from mika.conversation.evaluation.cases import VisibleTurn
from mika.conversation.participation import ParticipationDecision
from mika.conversation.tools import ToolPlan


@dataclass(frozen=True, slots=True)
class GenerationEvidence:
    """Facts recorded at the generation-stage boundary."""

    used_tools: tuple[str, ...] = ()
    media_context_used: bool = False


class EvidenceRecordingGenerator:
    """Record actual staged inputs while delegating generation."""

    def __init__(self, delegate: TurnGenerator) -> None:
        self._delegate = delegate
        self._evidence: dict[str, GenerationEvidence] = {}

    async def generate(
        self,
        envelope: ConversationEnvelope,
        context: SelectedContext,
        participation: ParticipationDecision,
        tools: ToolPlan,
    ) -> MikaTurn:
        self._evidence[envelope.message_id] = GenerationEvidence(
            tools.names,
            bool(envelope.visual_inputs),
        )
        return await self._delegate.generate(envelope, context, participation, tools)

    def take(self, message_id: str) -> GenerationEvidence:
        """Consume evidence, returning empty evidence when generation was skipped."""
        return self._evidence.pop(message_id, GenerationEvidence())


def visible_from_action(action: ActionPlan, evidence: GenerationEvidence) -> VisibleTurn:
    """Build benchmark-visible output from action and generation stage facts."""
    actions: list[str] = []
    if action.reactions:
        actions.append("reaction")
    if action.media is not None:
        actions.append(action.media.kind)
    used_tools = evidence.used_tools
    if action.media is not None and "media_search" not in used_tools:
        used_tools = (*used_tools, "media_search")
    return VisibleTurn(
        reply=action.reply,
        actions=tuple(actions),
        used_tools=used_tools,
        used_media_context=evidence.media_context_used,
    )
