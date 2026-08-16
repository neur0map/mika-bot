"""Context selection and post-turn observation behavior."""

from __future__ import annotations

from datetime import UTC, datetime

from mika.conversation.context import ContextSelector, TurnObservation, TurnObserver
from mika.conversation.context.retrieval import MemoryRecall
from mika.conversation.contracts import ConversationEnvelope


class MemoryStore:
    """In-memory implementation of the context storage contract."""

    def __init__(self) -> None:
        self.rows = [
            ("user", "alice", "one"),
            ("assistant", "mika", "first assistant phrase"),
            ("user", "ben", "two"),
            ("assistant", "mika", "second assistant phrase"),
        ]
        self.remembered: list[dict[str, str]] = []

    async def recent(self, channel_id: str) -> list[tuple[str, str, str]]:
        return self.rows

    async def remember(self, **values: str) -> None:
        self.remembered.append(values)


def envelope() -> ConversationEnvelope:
    return ConversationEnvelope(
        message_id="m1",
        channel_id="c1",
        guild_id="g1",
        author_id="u1",
        author_name="alice",
        text="new message",
        mentioned=False,
        created_at=datetime(2026, 8, 16, tzinfo=UTC),
    )


async def test_selector_preserves_order_names_and_bounded_assistant_phrases() -> None:
    selected = await ContextSelector(MemoryStore(), phrase_limit=1).select(envelope())

    assert [(item.role, item.author_name, item.content) for item in selected.history] == [
        ("user", "alice", "one"),
        ("assistant", "mika", "first assistant phrase"),
        ("user", "ben", "two"),
        ("assistant", "mika", "second assistant phrase"),
    ]
    assert selected.avoid_phrases == ("second assistant phrase",)
    assert selected.trace_details == {"history_count": 4, "avoid_phrase_count": 1}


async def test_selector_includes_retrieved_memory_and_count_only_trace_details() -> None:
    class Retriever:
        async def retrieve(self, incoming: ConversationEnvelope) -> MemoryRecall:
            return MemoryRecall("favorite game: Hades", 1, 2, 3)

    selected = await ContextSelector(MemoryStore(), retriever=Retriever()).select(envelope())

    assert selected.memory == "favorite game: Hades"
    assert selected.trace_details == {
        "history_count": 4,
        "avoid_phrase_count": 2,
        "fact_count": 1,
        "match_count": 2,
        "feedback_count": 3,
    }


async def test_observer_persists_visible_user_and_assistant_turns() -> None:
    memory = MemoryStore()
    observer = TurnObserver(memory)

    await observer.observe(
        TurnObservation(envelope=envelope(), reply="short answer", intent="chat", confidence=0.8)
    )

    assert memory.remembered == [
        {
            "channel_id": "c1",
            "author_id": "u1",
            "author_name": "alice",
            "role": "user",
            "content": "new message",
        },
        {
            "channel_id": "c1",
            "author_id": "mika",
            "author_name": "mika",
            "role": "assistant",
            "content": "short answer",
        },
    ]


async def test_observer_does_not_store_empty_assistant_reply() -> None:
    memory = MemoryStore()

    await TurnObserver(memory).observe(
        TurnObservation(envelope=envelope(), reply="", intent="silence", confidence=0.9)
    )

    assert len(memory.remembered) == 1
    assert memory.remembered[0]["role"] == "user"


async def test_observer_learns_only_explicit_user_facts() -> None:
    class Facts:
        def __init__(self) -> None:
            self.items: list[tuple[str, str, str, str]] = []

        async def upsert_fact(
            self, user_id: str, fact_key: str, fact_value: str, source_message_id: str
        ) -> None:
            self.items.append((user_id, fact_key, fact_value, source_message_id))

    facts = Facts()
    explicit = envelope()
    explicit = ConversationEnvelope(
        explicit.message_id,
        explicit.channel_id,
        explicit.guild_id,
        explicit.author_id,
        explicit.author_name,
        "actually my favorite game is Hades II",
        explicit.mentioned,
        explicit.created_at,
    )

    await TurnObserver(MemoryStore(), facts=facts).observe(
        TurnObservation(explicit, "nice", "chat", 0.8)
    )

    assert facts.items == [("u1", "favorite_game", "Hades II", "m1")]
