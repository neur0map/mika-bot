"""Typed orchestration for one conversation turn."""

from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from mika.ai.llm.turn import MikaTurn
from mika.conversation.actions import ActionContext, ActionPlan, ActionPlanner, ExecutionResult
from mika.conversation.context import (
    ContextSelector,
    SelectedContext,
    TurnObservation,
    TurnObserver,
)
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.participation import ParticipationDecision, ParticipationPlanner
from mika.conversation.tools import ToolPlan, ToolPlanner
from mika.conversation.trace_service import TraceRepository, TurnTraceService


class TurnGenerator(Protocol):
    """Generation capability consumed by the engine."""

    async def generate(
        self,
        envelope: ConversationEnvelope,
        context: SelectedContext,
        participation: ParticipationDecision,
        tools: ToolPlan,
    ) -> MikaTurn: ...


class ConversationEngine:
    """Run deterministic stages around one externally generated candidate."""

    def __init__(
        self,
        context: ContextSelector,
        participation: ParticipationPlanner,
        tools: ToolPlanner,
        generator: TurnGenerator,
        actions: ActionPlanner,
        observer: TurnObserver,
        traces: TraceRepository,
    ) -> None:
        self._context = context
        self._participation = participation
        self._tools = tools
        self._generator = generator
        self._actions = actions
        self._observer = observer
        self._traces = traces
        self._pending: dict[str, TurnTraceService] = {}

    async def handle(self, envelope: ConversationEnvelope) -> ActionPlan:
        """Select context and produce a platform-neutral visible-action plan."""
        trace = TurnTraceService(str(uuid4()), envelope.message_id, envelope.channel_id)
        trace.record(
            "ingress",
            "ready",
            details={"media_count": len(envelope.visual_inputs), "mentioned": envelope.mentioned},
        )
        context_details: dict[str, object] = {}
        with trace.measure("context", details=context_details):
            selected = await self._context.select(envelope)
            context_details.update(selected.trace_details)
        participation = self._participation.plan(envelope, selected)
        trace.record(
            "participation",
            participation.mode,
            reason=participation.reason,
            details={"confidence": participation.confidence},
        )
        tool_plan = self._tools.plan(envelope, participation)
        trace.record("tools", "eligible" if tool_plan.names else "skipped", reason=tool_plan.reason)
        if participation.mode == "observe":
            turn = MikaTurn(reply="", intent="silence", confidence=participation.confidence)
            trace.record("generation", "skipped", reason=participation.reason)
        else:
            with trace.measure("generation", details={"tool_count": len(tool_plan.names)}):
                turn = await self._generator.generate(envelope, selected, participation, tool_plan)
        action_context = ActionContext(
            envelope.channel_id,
            envelope.mentioned,
            envelope.mentioned or envelope.text.rstrip().endswith("?"),
            participation.reason,
        )
        plan = self._actions.plan(turn, action_context)
        trace.record(
            "policy", "silent" if plan.is_silent else "allowed", reason=plan.silence_reason
        )
        self._pending[envelope.message_id] = trace
        return plan

    async def observe(
        self,
        envelope: ConversationEnvelope,
        action: ActionPlan,
        execution: ExecutionResult,
    ) -> None:
        """Learn from visible execution, advance cooldowns, and persist one trace."""
        self._actions.record_visible(action, execution, channel_id=envelope.channel_id)
        visible_reply = action.reply if execution.reply_message_id is not None else ""
        expression_observer = getattr(self._generator, "observe_expression", None)
        if expression_observer is not None and (visible_reply or execution.applied_reactions):
            expression_observer(
                envelope.channel_id,
                visible_reply,
                execution.applied_reactions,
            )
        await self._observer.observe(
            TurnObservation(envelope, visible_reply, action.intent, action.confidence)
        )
        trace = self._pending.pop(envelope.message_id, None)
        if trace is None:
            return
        visible = bool(
            execution.reply_message_id or execution.applied_reactions or execution.media_url
        )
        trace.record(
            "execution",
            "visible" if visible else "silent",
            details={
                "reply_sent": execution.reply_message_id is not None,
                "reaction_count": len(execution.applied_reactions),
                "media_sent": execution.media_url is not None,
                "failure_count": len(execution.failures),
            },
        )
        await trace.persist(self._traces)
