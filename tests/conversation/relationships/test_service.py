"""Relationship-memory orchestration across extraction, persistence, and recall."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.persistence.conversations.relationship_memory_test_support import (
    create_archive,
    inspection_factory,
    policy,
    repository,
)

from mika.conversation.context.retrieval import MemoryRecall
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.relationships.activation import ActivationPolicy
from mika.conversation.relationships.consolidation import RelationshipConsolidator
from mika.conversation.relationships.contracts import RelationDecision, RelationKind
from mika.conversation.relationships.extraction import EvidenceProposal
from mika.conversation.relationships.service import (
    ObservationInput,
    RelationshipMemoryService,
)
from mika.persistence.conversations.archive_reader import ArchiveReader
from mika.persistence.conversations.relationship_memory import RelationshipMemoryRepository
from mika.persistence.conversations.relationship_models import (
    StoredArchiveCursor,
    StoredClaim,
    StoredClaimEvidence,
    StoredProfileVersion,
    StoredRecallEvent,
)

NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)


class Extractor:
    """Controllable provider boundary with deterministic proposals."""

    def __init__(self, *, fail_message_id: str | None = None) -> None:
        self.fail_message_id = fail_message_id
        self.calls: list[str] = []

    async def extract(
        self, observation: ObservationInput, relation: RelationDecision
    ) -> tuple[EvidenceProposal, ...]:
        self.calls.append(observation.message_id)
        if observation.message_id == self.fail_message_id:
            raise RuntimeError("provider unavailable")
        value = "Celeste" if relation.relation == "correction" else "Hades"
        return (
            EvidenceProposal(
                "preference",
                "preference:game",
                value,
                "correction" if relation.relation == "correction" else "explicit",
                0.98,
                observation.message_id,
                observation.created_at,
                "fixture",
            ),
        )


class Classifier:
    """Deterministic relation boundary for correction tests."""

    def classify(self, observation: ObservationInput) -> RelationDecision:
        relation: RelationKind = (
            "correction" if observation.text.startswith("Actually") else "follow_up"
        )
        return RelationDecision(relation, 0.95, "fixture")


class Retriever:
    """Return the active scoped claim value as prompt memory."""

    def __init__(self, source: RelationshipMemoryRepository) -> None:
        self.source = source

    async def retrieve(self, envelope: ConversationEnvelope) -> MemoryRecall:
        claims = await self.source.claims_for_user(
            envelope.author_id,
            visibility_kind="guild",
            guild_id=envelope.guild_id,
            channel_id=envelope.channel_id,
        )
        return MemoryRecall(
            text=" | ".join(claim.value for claim in claims),
            relationship_retrieval=True,
            candidate_ids=tuple(claim.claim_id for claim in claims),
            selected_ids=tuple(claim.claim_id for claim in claims),
            selected_tiers={claim.claim_id: "index" for claim in claims},
            estimated_token_cost=len(claims),
        )


def observation(message_id: str, text: str = "I like Hades") -> ObservationInput:
    return ObservationInput(
        source_kind="discord",
        source_id=message_id,
        message_id=message_id,
        subject_user_id="user-1",
        text=text,
        created_at=NOW,
        visibility_kind="guild",
        guild_id="guild-1",
        channel_id="channel-1",
    )


def envelope(message_id: str = "turn-2") -> ConversationEnvelope:
    return ConversationEnvelope(
        message_id,
        "channel-1",
        "guild-1",
        "user-1",
        "Ada",
        "Do you remember my favorite game?",
        False,
        NOW + timedelta(minutes=2),
    )


async def service_for(
    path: Path, extractor: Extractor
) -> tuple[RelationshipMemoryService, RelationshipMemoryRepository, AsyncEngine]:
    store, engine = await repository(path)
    await store.write_policy_version(policy())
    service = RelationshipMemoryService(
        repository=store,
        extractor=extractor,
        activation_policy=ActivationPolicy(),
        classifier=Classifier(),
        retriever=Retriever(store),
        consolidator=RelationshipConsolidator(),
        batch_size=2,
        clock=lambda: NOW + timedelta(minutes=3),
    )
    return service, store, engine


async def test_pending_observations_are_bounded_and_cursor_idempotent(tmp_path: Path) -> None:
    archive_path = tmp_path / "archive.db"
    create_archive(archive_path)
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    service.pending_source = ArchiveReader(archive_path)
    try:
        first = await service.run_pending_observations()
        second = await service.run_pending_observations()

        assert (first.processed, first.remaining_hint) == (2, True)
        assert second.processed == 1
        cursor = await store.cursor("shared_archive")
        assert cursor is not None
        assert cursor.discord_message_id == "102"
        assert (await service.run_pending_observations()).processed == 0
    finally:
        await store.close()
        await engine.dispose()


async def test_failed_extraction_leaves_cursor_at_last_success(tmp_path: Path) -> None:
    archive_path = tmp_path / "archive.db"
    create_archive(archive_path)
    service, store, engine = await service_for(
        tmp_path / "memory.db", Extractor(fail_message_id="101")
    )
    service.pending_source = ArchiveReader(archive_path)
    try:
        result = await service.run_pending_observations()

        assert result.processed == 1
        assert result.failed_message_id == "101"
        cursor = await store.cursor("shared_archive")
        assert cursor is not None
        assert cursor.discord_message_id == "100"
    finally:
        await store.close()
        await engine.dispose()


async def test_correction_is_available_to_next_recall_and_trace_uses_policy(tmp_path: Path) -> None:
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        await service.observe_turn(observation("100"))
        await service.observe_turn(observation("101", "Actually, I prefer Celeste"))

        recalled = await service.recall(envelope())

        assert recalled.text == "Celeste"
        async with inspection_factory(engine)() as inspection:
            trace = await inspection.scalar(select(StoredRecallEvent))
            claims = list((await inspection.scalars(select(StoredClaim))).all())
        assert trace is not None
        assert trace.policy_version_id == "policy-1"
        assert trace.query_hash.startswith("sha256:")
        assert {claim.value: claim.state for claim in claims} == {
            "Hades": "superseded",
            "Celeste": "active",
        }
    finally:
        await store.close()
        await engine.dispose()


async def test_disabled_learning_performs_no_derived_writes(tmp_path: Path) -> None:
    store, engine = await repository(tmp_path / "memory.db")
    disabled = policy()
    disabled = disabled.__class__(
        disabled.policy_version_id,
        False,
        disabled.semantic_retrieval_enabled,
        disabled.provider_extraction_enabled,
        disabled.local_relation_model_enabled,
        disabled.visibility_rules,
        disabled.change_reason,
        disabled.created_at,
    )
    await store.write_policy_version(disabled)
    extractor = Extractor()
    service = RelationshipMemoryService(
        repository=store,
        extractor=extractor,
        activation_policy=ActivationPolicy(),
        classifier=Classifier(),
        retriever=Retriever(store),
        consolidator=RelationshipConsolidator(),
    )
    try:
        result = await service.observe_turn(observation("100"))

        async with inspection_factory(engine)() as inspection:
            counts = (
                await inspection.scalar(select(func.count()).select_from(StoredClaim)),
                await inspection.scalar(select(func.count()).select_from(StoredClaimEvidence)),
                await inspection.scalar(select(func.count()).select_from(StoredProfileVersion)),
                await inspection.scalar(select(func.count()).select_from(StoredRecallEvent)),
                await inspection.scalar(select(func.count()).select_from(StoredArchiveCursor)),
            )
        assert result.outcome == "disabled"
        assert counts == (0, 0, 0, 0, 0)
        assert extractor.calls == []
    finally:
        await store.close()
        await engine.dispose()


async def test_observation_records_effective_policy_version(tmp_path: Path) -> None:
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        result = await service.observe_turn(observation("100"))

        async with inspection_factory(engine)() as inspection:
            stored = await inspection.scalar(select(StoredClaimEvidence))
        assert result.policy_version_id == "policy-1"
        assert stored is not None
        assert stored.policy_version_id == "policy-1"
    finally:
        await store.close()
        await engine.dispose()


async def test_consolidation_reads_candidate_history_and_is_profile_idempotent(
    tmp_path: Path,
) -> None:
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        await service.observe_turn(observation("100"))

        first = await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )
        second = await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )

        async with inspection_factory(engine)() as inspection:
            count = await inspection.scalar(select(func.count()).select_from(StoredProfileVersion))
        assert first.profile_changed is True
        assert first.policy_version_id == "policy-1"
        assert second.profile_changed is False
        assert count == 1
    finally:
        await store.close()
        await engine.dispose()


@pytest.mark.parametrize("limit", [0, -1])
async def test_pending_observation_limit_must_be_positive(tmp_path: Path, limit: int) -> None:
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        with pytest.raises(ValueError, match="positive"):
            await service.run_pending_observations(limit=limit)
    finally:
        await store.close()
        await engine.dispose()
