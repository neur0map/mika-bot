"""End-to-end staged conversation engine contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mika.ai.llm.turn import MikaTurn
from mika.conversation.actions import ActionPlan, ActionPlanner, ExecutionResult
from mika.conversation.context import ContextSelector, MemoryRecall, MergedRetriever, TurnObserver
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
        self.observed: list[tuple[str, str, tuple[str, ...]]] = []
        self.contexts: list[SelectedContext] = []

    async def generate(
        self,
        envelope: ConversationEnvelope,
        context: SelectedContext,
        participation: ParticipationDecision,
        tools: ToolPlan,
    ) -> MikaTurn:
        self.tool_names = tools.names
        self.contexts.append(context)
        return MikaTurn(reply="sunny and 22°", intent="answer", confidence=0.9)

    def observe_expression(self, channel_id: str, reply: str, reactions: tuple[str, ...]) -> None:
        self.observed.append((channel_id, reply, reactions))


class Traces:
    def __init__(self) -> None:
        self.items: list[TurnTrace] = []

    async def add(self, trace: TurnTrace) -> None:
        self.items.append(trace)


class RelationshipSink:
    def __init__(self, memory: Memory) -> None:
        self.memory = memory
        self.submitted: list[tuple[str, list[tuple[str, str]]]] = []

    def submit(self, envelope: ConversationEnvelope) -> bool:
        self.submitted.append((envelope.message_id, list(self.memory.remembered)))
        return True


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
    assert generator.observed == [("2", "sunny and 22°", ())]
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
    assert generator.observed == []
    assert memory.remembered == [("user", "send me the address")]


async def test_relationship_observation_follows_generation_and_local_persistence() -> None:
    memory = Memory()
    generator = Generator()
    relationships = RelationshipSink(memory)
    engine = ConversationEngine(
        ContextSelector(memory),
        ParticipationPlanner(),
        ToolPlanner(),
        generator,
        ActionPlanner(),
        TurnObserver(memory, relationships=relationships),
        Traces(),
    )
    envelope = ConversationEnvelope(
        "visible-turn",
        "2",
        "3",
        "4",
        "Ada",
        "Mika, what's the weather today?",
        True,
        datetime.now(UTC),
    )

    plan = await engine.handle(envelope)
    assert relationships.submitted == []

    await engine.observe(envelope, plan, ExecutionResult("reply-1", (), None, ()))

    assert relationships.submitted == [
        (
            "visible-turn",
            [
                ("user", "Mika, what's the weather today?"),
                ("assistant", "sunny and 22°"),
            ],
        )
    ]


@pytest.mark.parametrize(
    ("action", "execution"),
    [
        (
            ActionPlan(reply="hello"),
            ExecutionResult(None, (), None, ("reply:HTTPException",)),
        ),
        (
            ActionPlan(silence_reason="model_silence"),
            ExecutionResult(None, (), None, ()),
        ),
    ],
)
async def test_failed_or_silent_execution_does_not_submit_relationship_observation(
    action: ActionPlan,
    execution: ExecutionResult,
) -> None:
    memory = Memory()
    relationships = RelationshipSink(memory)
    engine = ConversationEngine(
        ContextSelector(memory),
        ParticipationPlanner(),
        ToolPlanner(),
        Generator(),
        ActionPlanner(),
        TurnObserver(memory, relationships=relationships),
        Traces(),
    )
    envelope = ConversationEnvelope(
        "not-visible", "2", "3", "4", "Ada", "hello", False, datetime.now(UTC)
    )

    await engine.observe(envelope, action, execution)

    assert memory.remembered == [("user", "hello")]
    assert relationships.submitted == []


@pytest.mark.parametrize(
    "execution",
    [
        ExecutionResult("reply-1", (), None, ()),
        ExecutionResult(None, ("👀",), None, ()),
        ExecutionResult(None, (), "https://media.invalid/item", ()),
    ],
)
async def test_each_visible_execution_kind_submits_relationship_observation(
    execution: ExecutionResult,
) -> None:
    memory = Memory()
    relationships = RelationshipSink(memory)
    engine = ConversationEngine(
        ContextSelector(memory),
        ParticipationPlanner(),
        ToolPlanner(),
        Generator(),
        ActionPlanner(),
        TurnObserver(memory, relationships=relationships),
        Traces(),
    )
    envelope = ConversationEnvelope(
        "visible-kind", "2", "3", "4", "Ada", "hello", False, datetime.now(UTC)
    )

    await engine.observe(envelope, ActionPlan(reply="hello"), execution)

    assert [message_id for message_id, _ in relationships.submitted] == ["visible-kind"]


async def test_engine_generation_receives_merged_relationship_overview() -> None:
    class Retriever:
        def __init__(self, recall: MemoryRecall) -> None:
            self.recall = recall

        async def retrieve(self, envelope: ConversationEnvelope) -> MemoryRecall:
            return self.recall

    generator = Generator()
    engine = ConversationEngine(
        ContextSelector(
            Memory(),
            retriever=MergedRetriever(
                Retriever(MemoryRecall("local context")),
                Retriever(
                    MemoryRecall(
                        "relationship overview",
                        relationship_retrieval=True,
                        candidate_ids=("profile-1",),
                        selected_ids=("profile-1",),
                    )
                ),
            ),
        ),
        ParticipationPlanner(),
        ToolPlanner(),
        generator,
        ActionPlanner(),
        TurnObserver(Memory()),
        Traces(),
    )
    envelope = ConversationEnvelope(
        "memory-turn",
        "2",
        "3",
        "4",
        "Ada",
        "Mika, do you remember?",
        True,
        datetime.now(UTC),
    )

    await engine.handle(envelope)

    assert generator.contexts[0].memory == "local context\n\nrelationship overview"
    assert generator.contexts[0].relationship_retrieval is True
    assert generator.contexts[0].selected_ids == ("profile-1",)
