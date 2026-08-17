"""Explicit fact extraction and bounded affinity retrieval."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from mika.conversation.context.contracts import MemoryCandidate
from mika.conversation.context.facts import extract_explicit_facts
from mika.conversation.context.retrieval import AffinityRetriever, MemoryRecall, MergedRetriever
from mika.conversation.contracts import ConversationEnvelope
from mika.persistence.conversations.relationship_records import (
    ClaimRecord,
    ProfileVersionRecord,
)


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


def _claim(
    claim_id: str,
    value: str,
    *,
    subject_user_id: str = "u1",
    visibility_kind: str = "channel",
    guild_id: str | None = "g1",
    channel_id: str | None = "c1",
    evidence_class: str = "explicit",
) -> ClaimRecord:
    observed_at = datetime(2026, 8, 10, tzinfo=UTC)
    return ClaimRecord(
        claim_id=claim_id,
        subject_user_id=subject_user_id,
        visibility_kind=visibility_kind,
        guild_id=guild_id,
        channel_id=channel_id,
        kind="preference",
        key="favorite_game",
        value=value,
        evidence_class=evidence_class,
        confidence=0.95,
        state="active",
        predecessor_claim_id=None,
        source_message_ids=(f"source-{claim_id}",),
        observation_count=1,
        first_observed_at=observed_at,
        last_observed_at=observed_at,
        last_confirmed_at=observed_at,
    )


class RelationshipSource:
    def __init__(
        self,
        claims: tuple[ClaimRecord, ...] = (),
        profile: ProfileVersionRecord | None = None,
    ) -> None:
        self.claims = claims
        self.profile = profile

    async def claims_for_user(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
        limit: int = 100,
    ) -> tuple[ClaimRecord, ...]:
        return self.claims

    async def active_profile(self, subject_user_id: str) -> ProfileVersionRecord | None:
        return self.profile


class ScopedSource(Source):
    def __init__(self, candidates: tuple[SimpleNamespace, ...] = ()) -> None:
        self._candidates = candidates
        self.fact_calls = 0

    async def facts(self, user_id: str, *, limit: int = 12) -> list[tuple[str, str]]:
        self.fact_calls += 1
        return [("legacy_secret", "must never render")]

    async def candidates(
        self, channel_id: str, author_id: str, *, limit: int = 80
    ) -> tuple[SimpleNamespace, ...]:
        return self._candidates


def _message(
    message_id: int,
    content: str,
    *,
    author_id: str = "u1",
    channel_id: str = "c1",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=message_id,
        channel_id=channel_id,
        author_id=author_id,
        author_name="Ada",
        content=content,
        created_at=datetime.now(UTC) - timedelta(days=1),
    )


async def test_relationship_retrieval_keeps_person_attribution_and_public_scope_strict() -> None:
    relationships = RelationshipSource(
        (
            _claim("visible", "Hades II"),
            _claim("other-person", "private favorite", subject_user_id="u2"),
            _claim(
                "dm-secret",
                "DM-only detail",
                visibility_kind="direct_message",
                guild_id=None,
                channel_id="dm1",
            ),
            _claim("other-channel", "channel secret", channel_id="c9"),
        )
    )
    source = ScopedSource()

    recall = await AffinityRetriever(source, relationship_source=relationships).retrieve(
        _envelope("favorite game")
    )

    assert "Hades II" in recall.text
    assert "private favorite" not in recall.text
    assert "DM-only detail" not in recall.text
    assert "channel secret" not in recall.text
    assert recall.selected_ids == ("visible",)
    assert recall.rejection_reasons["other-person"] == "subject_mismatch"
    assert recall.rejection_reasons["dm-secret"] == "direct_message_scope_mismatch"


async def test_unscoped_aggregate_profile_never_leaks_private_guild_content_into_dm() -> None:
    profile = ProfileVersionRecord(
        "profile-private",
        "u1",
        "private guild launch",
        "private guild launch details",
        "v1",
        "v1",
        "policy-1",
        datetime(2026, 8, 17, tzinfo=UTC),
    )
    dm = ConversationEnvelope("dm", "dm1", "", "u1", "Ada", "launch", True, datetime.now(UTC))

    recall = await AffinityRetriever(
        ScopedSource(), relationship_source=RelationshipSource(profile=profile), minimum_score=0.0
    ).retrieve(dm)

    assert "private guild" not in recall.text
    assert f"profile:{profile.profile_version_id}" not in recall.candidate_ids


async def test_same_scope_claim_recall_remains_available_without_aggregate_profiles() -> None:
    recall = await AffinityRetriever(
        ScopedSource(),
        relationship_source=RelationshipSource((_claim("same-scope", "Hades II"),)),
        minimum_score=0.0,
    ).retrieve(_envelope("Hades"))

    assert "Hades II" in recall.text
    assert recall.selected_ids == ("same-scope",)


async def test_relationship_mode_rejects_legacy_unscoped_facts_instead_of_falling_back() -> None:
    source = ScopedSource()

    recall = await AffinityRetriever(source, relationship_source=RelationshipSource()).retrieve(
        _envelope()
    )

    assert source.fact_calls == 0
    assert "must never render" not in recall.text
    assert recall.fact_count == 0
    assert recall.trace_details["estimated_token_cost"] == 0
    assert recall.trace_details["latency_ms"] >= 0


async def test_relationship_source_failure_fails_open_without_legacy_fallback() -> None:
    class BrokenRelationshipSource(RelationshipSource):
        async def claims_for_user(
            self,
            subject_user_id: str,
            *,
            visibility_kind: str,
            guild_id: str | None,
            channel_id: str | None,
            limit: int = 100,
        ) -> tuple[ClaimRecord, ...]:
            raise RuntimeError("relationship store unavailable")

    source = ScopedSource()

    recall = await AffinityRetriever(
        source, relationship_source=BrokenRelationshipSource()
    ).retrieve(_envelope())

    assert recall.text == ""
    assert recall.relationship_retrieval is True
    assert source.fact_calls == 0
    assert recall.trace_details["latency_ms"] >= 0


async def test_local_relationship_recall_rejects_irrelevant_messages_without_semantics() -> None:
    source = ScopedSource(
        (
            _message(1, "our launch joke landed well"),
            _message(2, "watering the garden"),
            _message(3, "someone else's launch", author_id="u2"),
        )
    )

    recall = await AffinityRetriever(source, relationship_source=RelationshipSource()).retrieve(
        _envelope("remember the launch joke")
    )

    assert "our launch joke landed well" in recall.text
    assert "watering the garden" not in recall.text
    assert "someone else's launch" not in recall.text
    assert recall.selected_ids == ("message:1",)
    assert recall.rejection_reasons["message:2"] == "below_minimum_score"
    assert recall.rejection_reasons["message:3"] == "subject_mismatch"


async def test_breadth_first_budget_fits_each_non_anchor_before_deepening() -> None:
    now = datetime(2026, 8, 17, tzinfo=UTC)
    candidates = (
        MemoryCandidate(
            "first",
            "u1",
            "channel",
            "g1",
            "c1",
            "claim",
            "first index",
            "first overview has six useful words",
            None,
            "repeated_behavior",
            0.9,
            now,
        ),
        MemoryCandidate(
            "second",
            "u1",
            "channel",
            "g1",
            "c1",
            "claim",
            "second index",
            "second overview has six useful words",
            None,
            "repeated_behavior",
            0.8,
            now,
        ),
    )
    source = ScopedSource()

    recall = await AffinityRetriever(
        source,
        relationship_source=RelationshipSource(),
        relationship_candidates=candidates,
        token_budget=8,
        minimum_score=0.0,
    ).retrieve(_envelope("index"))

    assert recall.selected_ids == ("first", "second")
    assert recall.selected_tiers == {"first": "index", "second": "index"}
    assert recall.estimated_token_cost == 8
    assert "first index" in recall.text
    assert "second index" in recall.text


async def test_per_entry_cap_downgrades_to_precomputed_tier_without_slicing() -> None:
    now = datetime(2026, 8, 17, tzinfo=UTC)
    candidate = MemoryCandidate(
        "bounded",
        "u1",
        "channel",
        "g1",
        "c1",
        "claim",
        "safe compact index",
        "overview representation is deliberately much too large",
        None,
        "explicit",
        1.0,
        now,
    )

    recall = await AffinityRetriever(
        ScopedSource(),
        relationship_source=RelationshipSource(),
        relationship_candidates=(candidate,),
        token_budget=20,
        per_entry_token_cap=3,
        minimum_score=0.0,
    ).retrieve(_envelope("compact"))

    assert recall.selected_tiers == {"bounded": "index"}
    assert recall.text.endswith("safe compact index")
    assert "overview representation" not in recall.text
    assert recall.rejection_reasons["bounded"] == "per_entry_cap:overview->index"


async def test_merged_recall_deduplicates_context_and_fails_open() -> None:
    class StaticRetriever:
        def __init__(self, recall: MemoryRecall) -> None:
            self.recall = recall

        async def retrieve(self, envelope: ConversationEnvelope) -> MemoryRecall:
            return self.recall

    class BrokenRetriever:
        async def retrieve(self, envelope: ConversationEnvelope) -> MemoryRecall:
            raise RuntimeError("relationship store unavailable")

    merged = MergedRetriever(
        StaticRetriever(MemoryRecall("Known fact\n\nShared context", fact_count=1)),
        BrokenRetriever(),
        StaticRetriever(
            MemoryRecall(
                "Shared context\n\nRelationship overview",
                relationship_retrieval=True,
                candidate_ids=("profile-1",),
                selected_ids=("profile-1",),
            )
        ),
    )

    recall = await merged.retrieve(_envelope())

    assert recall.text == "Known fact\n\nShared context\n\nRelationship overview"
    assert recall.fact_count == 1
    assert recall.relationship_retrieval is True
    assert recall.selected_ids == ("profile-1",)
