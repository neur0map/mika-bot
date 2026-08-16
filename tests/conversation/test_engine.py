"""End-to-end staged conversation engine contracts."""

from __future__ import annotations

from datetime import UTC, datetime

from mika.ai.llm.turn import MikaTurn
from mika.conversation.actions import ActionPlanner, ExecutionResult
from mika.conversation.context import ContextSelector, TurnObserver
from mika.conversation.context.contracts import SelectedContext
from mika.conversation.contracts import ConversationEnvelope, TurnTrace
from mika.conversation.engine import ConversationEngine
from mika.conversation.participation import ParticipationDecision, ParticipationPlanner
from mika.conversation.tools import ToolPlan, ToolPlanner


class Memory:
    def __init__(self) -> None:
        self.rows = [("assistant", "Mika", "older reply")]
        self.remembered: list[tuple[str, str]] = []

    async def recent(self, channel_id: str) -> list[tuple[str, str, str]]:
        return self.rows

    async def remember(self, **values: str) -> None:
        self.remembered.append((values["role"], values["content"]))


class Generator:
    def __init__(self) -> None:
        self.tool_names: tuple[str, ...] = ()

    async def generate(
        self,
        envelope: ConversationEnvelope,
        context: SelectedContext,
        participation: ParticipationDecision,
        tools: ToolPlan,
    ) -> MikaTurn:
        self.tool_names = tools.names
        return MikaTurn(reply="sunny and 22°", intent="answer", confidence=0.9)


class Traces:
    def __init__(self) -> None:
        self.items: list[TurnTrace] = []

    async def add(self, trace: TurnTrace) -> None:
        self.items.append(trace)


async def test_engine_runs_stages_and_observes_only_visible_reply() -> None:
    memory = Memory()
    generator = Generator()
    traces = Traces()
    engine = ConversationEngine(
        ContextSelector(memory),
        ParticipationPlanner(),
        ToolPlanner(),
        generator,
        ActionPlanner(),
        TurnObserver(memory),
        traces,
    )
    envelope = ConversationEnvelope(
        "1",
        "2",
        "3",
        "4",
        "Ada",
        "Mika, what's the weather today?",
        True,
        datetime.now(UTC),
    )

    plan = await engine.handle(envelope)
    await engine.observe(envelope, plan, ExecutionResult("9", (), None, ()))

    assert plan.reply == "sunny and 22°"
    assert generator.tool_names == ("web_search",)
    assert memory.remembered == [
        ("user", "Mika, what's the weather today?"),
        ("assistant", "sunny and 22°"),
    ]
    assert len(traces.items) == 1
    assert [stage.stage for stage in traces.items[0].stages] == [
        "ingress",
        "context",
        "participation",
        "tools",
        "generation",
        "policy",
        "execution",
    ]


async def test_engine_skips_generation_when_observing() -> None:
    memory = Memory()
    generator = Generator()
    traces = Traces()
    engine = ConversationEngine(
        ContextSelector(memory),
        ParticipationPlanner(),
        ToolPlanner(),
        generator,
        ActionPlanner(),
        TurnObserver(memory),
        traces,
    )
    envelope = ConversationEnvelope(
        "1", "2", "3", "4", "Ada", "send me the address", False, datetime.now(UTC)
    )

    plan = await engine.handle(envelope)
    await engine.observe(envelope, plan, ExecutionResult(None, (), None, ()))

    assert plan.is_silent
    assert generator.tool_names == ()
    assert memory.remembered == [("user", "send me the address")]
