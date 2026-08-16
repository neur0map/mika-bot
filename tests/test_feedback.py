"""Learning feedback normalization."""

from __future__ import annotations

from types import SimpleNamespace

from mika.ai.learning.feedback import reaction_signal
from mika.bot.events.reactions import _learn_feedback


def test_reaction_signal_maps_common_feedback() -> None:
    assert reaction_signal("👍") == "positive"
    assert reaction_signal("💀") == "laugh"
    assert reaction_signal("🤔") == "confused"
    assert reaction_signal("👎") == "negative"
    assert reaction_signal("🫠") == "other"


async def test_local_feedback_learns_only_reactions_to_mika() -> None:
    class Memory:
        def __init__(self) -> None:
            self.items: list[tuple[str, ...]] = []

        async def add_feedback(self, *values: str) -> None:
            self.items.append(values)

    memory = Memory()
    bot = SimpleNamespace(user=SimpleNamespace(id=7), social_memory=memory)
    mika_message = SimpleNamespace(id=9, channel=SimpleNamespace(id=3), author=bot.user)
    human_message = SimpleNamespace(
        id=10, channel=SimpleNamespace(id=3), author=SimpleNamespace(id=8)
    )

    assert await _learn_feedback(bot, mika_message, "u1", "🔥", "positive") is True
    assert await _learn_feedback(bot, human_message, "u1", "🔥", "positive") is False
    assert memory.items == [("9", "3", "u1", "🔥", "positive")]
