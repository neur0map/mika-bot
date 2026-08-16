"""Explicit fact extraction and bounded affinity retrieval."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from mika.conversation.context.facts import extract_explicit_facts
from mika.conversation.context.retrieval import AffinityRetriever
from mika.conversation.contracts import ConversationEnvelope


def _envelope(text: str = "remember that launch joke?") -> ConversationEnvelope:
    return ConversationEnvelope("m1", "c1", "g1", "u1", "Ada", text, True, datetime.now(UTC))


def test_fact_extraction_is_explicit_and_correction_keys_are_stable() -> None:
    assert extract_explicit_facts("my favorite game is Hades") == (("favorite_game", "Hades"),)
    assert extract_explicit_facts("actually my favorite game is Hades II") == (
        ("favorite_game", "Hades II"),
    )
    assert extract_explicit_facts("maybe Hades is good") == ()


class Source:
    async def facts(self, user_id: str, *, limit: int = 12) -> list[tuple[str, str]]:
        return [("favorite_game", "Hades II")]

    async def candidates(
        self, channel_id: str, author_id: str, *, limit: int = 80
    ) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                channel_id="c9", author_id="u1", author_name="Ada", content="our launch joke"
            ),
            SimpleNamespace(
                channel_id="c1", author_id="u2", author_name="Ben", content="launch was delayed"
            ),
            SimpleNamespace(
                channel_id="c9", author_id="u9", author_name="Nope", content="unrelated secret"
            ),
        ]

    async def feedback_summary(self, channel_id: str, *, limit: int = 100) -> dict[str, int]:
        return {"laugh": 3, "negative": 1}


async def test_retrieval_ranks_same_user_and_channel_lexical_context() -> None:
    recall = await AffinityRetriever(Source()).retrieve(_envelope())

    assert "Hades II" in recall.text
    assert "our launch joke" in recall.text
    assert "launch was delayed" in recall.text
    assert "unrelated secret" not in recall.text
    assert recall.fact_count == 1
    assert recall.match_count == 2
    assert recall.feedback_count == 4


async def test_retrieval_is_bounded_and_trace_details_are_counts_only() -> None:
    recall = await AffinityRetriever(Source(), match_limit=1).retrieve(_envelope())

    assert recall.match_count == 1
    assert recall.trace_details == {"fact_count": 1, "match_count": 1, "feedback_count": 4}
    assert "launch" not in repr(recall.trace_details)
