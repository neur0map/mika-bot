"""Context selection and post-turn observation behavior."""

from __future__ import annotations

from datetime import UTC, datetime

from mika.conversation.context import ContextSelector, TurnObservation, TurnObserver
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
