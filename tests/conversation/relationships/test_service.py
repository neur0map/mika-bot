"""Relationship-memory orchestration across extraction, persistence, and recall."""

from __future__ import annotations

from dataclasses import replace
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
from mika.conversation.relationships import service as service_module
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
from mika.persistence.conversations.relationship_records import (
    ArchiveSourceRecord,
    ClaimWrite,
    EvidenceWrite,
)

NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)


def test_relationship_service_stays_below_repository_file_cap() -> None:
    assert len(Path(service_module.__file__).read_text().splitlines()) < 500


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
        drink_correction = "chamomile" in observation.text.casefold()
        value = (
            "Chamomile"
            if drink_correction
            else "Celeste"
            if relation.relation == "correction"
            else "Hades"
        )
        key = " Preference:Drink " if drink_correction else "preference:game"
        return (
            EvidenceProposal(
                "preference",
                key,
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


class FailingExtractor(Extractor):
    async def extract(
        self, observation: ObservationInput, relation: RelationDecision
    ) -> tuple[EvidenceProposal, ...]:
        raise RuntimeError("provider unavailable")


class FallbackExtractor(Extractor):
    async def extract(
        self, observation: ObservationInput, relation: RelationDecision
    ) -> tuple[EvidenceProposal, ...]:
        proposal = (await super().extract(observation, relation))[0]
        return (replace(proposal, reason="provider_fallback:invalid_output:fixture"),)


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


def claim_write(
    claim_id: str,
    *,
    key: str,
    value: str,
    evidence_class: str,
    guild_id: str,
    channel_id: str,
    observed_at: datetime = NOW,
) -> ClaimWrite:
    return ClaimWrite(
        claim_id,
        "user-1",
        "guild",
        guild_id,
        channel_id,
        "preference",
        key,
        value,
        evidence_class,
        0.95,
        "candidate",
        None,
        observed_at,
    )


def evidence_write(
    source_id: str, *, guild_id: str, channel_id: str, observed_at: datetime = NOW
) -> EvidenceWrite:
    return EvidenceWrite(
        "discord",
        source_id,
        source_id,
        observed_at,
        "guild",
        guild_id,
        channel_id,
        "policy-1",
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
        claims = await store.claims_for_subject("user-1")
        assert claims
        assert {claim.state for claim in claims} == {"candidate"}
        assert (await service.run_pending_observations()).processed == 0
    finally:
        await store.close()
        await engine.dispose()


async def test_archive_observation_respects_disabled_direct_messages(tmp_path: Path) -> None:
    store, engine = await repository(tmp_path / "memory.db")
    await store.write_policy_version(
        replace(policy(), visibility_rules={"direct_message": False, "guild": True})
    )
    extractor = Extractor()
    service = RelationshipMemoryService(
        repository=store,
        extractor=extractor,
        activation_policy=ActivationPolicy(),
        classifier=Classifier(),
        retriever=Retriever(store),
        consolidator=RelationshipConsolidator(),
    )
    source = ArchiveSourceRecord(
        "discord",
        "dm-source",
        "900",
        "user-1",
        "Ada",
        "I like Hades",
        NOW,
        "direct_message",
        None,
        "dm-channel",
    )
    try:
        result = await service.observe_archive_candidate(source)
        assert result.outcome == "disabled"
        assert extractor.calls == []
        assert await store.claims_for_subject("user-1") == []
    finally:
        await store.close()
        await engine.dispose()


async def test_archive_downgrades_global_behavior_to_physical_channel(tmp_path: Path) -> None:
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    source = ArchiveSourceRecord(
        "discord",
        "behavior-source",
        "901",
        "user-1",
        "Ada",
        "I like Hades",
        NOW,
        "global_explicit",
        "guild-1",
        "channel-1",
    )

    class BehaviorExtractor(Extractor):
        async def extract(
            self, observation: ObservationInput, relation: RelationDecision
        ) -> tuple[EvidenceProposal, ...]:
            return (
                EvidenceProposal(
                    "expression",
                    "expression:emoji",
                    "often",
                    "repeated_behavior",
                    0.5,
                    observation.message_id,
                    observation.created_at,
                    "fixture",
                ),
            )

    service._extractor = BehaviorExtractor()
    try:
        await service.observe_archive_candidate(source)
        stored = (await store.claims_for_subject("user-1"))[0]
        assert (stored.visibility_kind, stored.guild_id, stored.channel_id) == (
            "channel",
            "guild-1",
            "channel-1",
        )
    finally:
        await store.close()
        await engine.dispose()


async def test_archive_global_correction_replaces_explicit_value_in_guild_and_dm_recall(
    tmp_path: Path,
) -> None:
    class GlobalExtractor(Extractor):
        async def extract(
            self, observation: ObservationInput, relation: RelationDecision
        ) -> tuple[EvidenceProposal, ...]:
            return (
                EvidenceProposal(
                    "preference",
                    "preference:drink",
                    "coffee" if relation.relation == "correction" else "tea",
                    "correction" if relation.relation == "correction" else "explicit",
                    0.98,
                    observation.message_id,
                    observation.created_at,
                    "fixture",
                ),
            )

    service, store, engine = await service_for(tmp_path / "memory.db", GlobalExtractor())
    first = ArchiveSourceRecord(
        "discord",
        "global-a",
        "910",
        "user-1",
        "Ada",
        "I prefer tea",
        NOW,
        "global_explicit",
        None,
        None,
    )
    correction = ArchiveSourceRecord(
        "discord",
        "global-b",
        "911",
        "user-1",
        "Ada",
        "Actually I prefer coffee",
        NOW + timedelta(minutes=1),
        "global_explicit",
        None,
        None,
    )
    try:
        await service.observe_archive_candidate(first)
        await service.observe_archive_candidate(correction)
        await service.consolidate_user(
            "user-1",
            visibility_kind="global_explicit",
            guild_id=None,
            channel_id=None,
        )

        guild_recall = await service.recall(envelope("guild-recall"))
        dm_envelope = replace(envelope("dm-recall"), guild_id="", channel_id="dm-channel")
        dm_recall = await service.recall(dm_envelope)

        assert guild_recall.text == "coffee"
        assert dm_recall.text == "coffee"
        claims = await store.claims_for_subject("user-1")
        assert {(claim.value, claim.state) for claim in claims} == {
            ("tea", "superseded"),
            ("coffee", "active"),
        }
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


async def test_shadow_mode_measures_recall_without_injecting_relationship_text(
    tmp_path: Path,
) -> None:
    store, engine = await repository(tmp_path / "memory.db")
    await store.write_policy_version(
        replace(policy(), visibility_rules={"dm_to_public": False, "shadow_mode": True})
    )
    service = RelationshipMemoryService(
        repository=store,
        extractor=Extractor(),
        activation_policy=ActivationPolicy(),
        classifier=Classifier(),
        retriever=Retriever(store),
        consolidator=RelationshipConsolidator(),
    )
    try:
        await service.observe_turn(observation("100"))

        recalled = await service.recall(envelope())

        async with inspection_factory(engine)() as inspection:
            trace = await inspection.scalar(select(StoredRecallEvent))
        assert recalled.text == ""
        assert recalled.relationship_retrieval is True
        assert trace is not None
        assert trace.selected_claim_ids_json != "[]"
    finally:
        await store.close()
        await engine.dispose()


async def test_service_emits_one_content_free_record_per_operation(tmp_path: Path) -> None:
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        await service.observe_turn(observation("telemetry-source"))
        await service.recall(envelope("telemetry-recall"))
        await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )

        records = service.telemetry.records
        assert [record.operation for record in records] == [
            "observation",
            "retrieval",
            "consolidation",
        ]
        assert all("telemetry-source" not in repr(record) for record in records)
        assert all(record.policy_version_id == "policy-1" for record in records)
        assert set(records[0].phase_durations_ms) >= {"policy", "extraction", "repository"}
        assert set(records[1].phase_durations_ms) >= {"policy", "ranking", "repository"}
        assert set(records[2].phase_durations_ms) >= {
            "policy",
            "repository_read",
            "consolidation",
            "publication",
            "cadence",
        }
    finally:
        await store.close()
        await engine.dispose()


async def test_no_profile_consolidation_persists_independent_cadence(tmp_path: Path) -> None:
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        run = await service.consolidate_user(
            "user-without-claims",
            visibility_kind="guild",
            guild_id="guild-1",
            channel_id="channel-1",
        )

        assert run.profile_version_id is None
        assert await service.last_consolidated_at("user-without-claims") is not None
    finally:
        await store.close()
        await engine.dispose()


async def test_failure_and_provider_fallback_keep_operation_phase_metadata(
    tmp_path: Path,
) -> None:
    failed, failed_store, failed_engine = await service_for(
        tmp_path / "failed.db", FailingExtractor()
    )
    fallback, fallback_store, fallback_engine = await service_for(
        tmp_path / "fallback.db", FallbackExtractor()
    )
    try:
        with pytest.raises(RuntimeError, match="provider unavailable"):
            await failed.observe_turn(observation("failed-source"))
        await fallback.observe_turn(observation("fallback-source"))

        failure_record = failed.telemetry.records[0]
        fallback_record = fallback.telemetry.records[0]
        assert set(failure_record.phase_durations_ms) >= {"policy", "extraction"}
        assert failure_record.fallback_reason == "RuntimeError"
        assert fallback_record.fallback_reason == "provider_fallback:invalid_output:fixture"
    finally:
        await failed_store.close()
        await failed_engine.dispose()
        await fallback_store.close()
        await fallback_engine.dispose()


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


async def test_consolidation_does_not_share_evidence_between_same_key_claims(
    tmp_path: Path,
) -> None:
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        await store.add_evidence(
            claim_write(
                "explicit",
                key="preference:drink",
                value="tea",
                evidence_class="explicit",
                guild_id="guild-1",
                channel_id="channel-1",
            ),
            evidence_write("source-explicit", guild_id="guild-1", channel_id="channel-1"),
        )
        await store.add_evidence(
            claim_write(
                "behavior",
                key="preference:drink",
                value="coffee",
                evidence_class="repeated_behavior",
                guild_id="guild-2",
                channel_id="channel-2",
            ),
            evidence_write("source-behavior", guild_id="guild-2", channel_id="channel-2"),
        )

        await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )

        explicit = await store.claim("explicit")
        behavior = await store.claim("behavior")
        assert explicit is not None and explicit.state == "active"
        assert behavior is not None and behavior.state == "candidate"
    finally:
        await store.close()
        await engine.dispose()


async def test_consolidation_keeps_independent_profile_heads_and_cadence_per_scope(
    tmp_path: Path,
) -> None:
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        for suffix, guild_id, channel_id, value in (
            ("one", "guild-1", "channel-1", "tea"),
            ("two", "guild-2", "channel-2", "coffee"),
        ):
            await store.add_evidence(
                claim_write(
                    suffix,
                    key=f"preference:drink:{suffix}",
                    value=value,
                    evidence_class="explicit",
                    guild_id=guild_id,
                    channel_id=channel_id,
                ),
                evidence_write(f"source-{suffix}", guild_id=guild_id, channel_id=channel_id),
            )
            await store.activate_claim(suffix, confirmed_at=NOW)

        await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )
        first_cadence = await service.last_consolidated_at(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )
        await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-2", channel_id="channel-2"
        )

        first = await store.active_profile_for_scope(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )
        second = await store.active_profile_for_scope(
            "user-1", visibility_kind="guild", guild_id="guild-2", channel_id="channel-2"
        )
        assert first is not None and "tea" in first.overview_text
        assert second is not None and "coffee" in second.overview_text
        assert first.profile_version_id != second.profile_version_id
        assert first_cadence is not None
        assert (
            await service.last_consolidated_at(
                "user-1", visibility_kind="guild", guild_id="guild-2", channel_id="channel-2"
            )
            is not None
        )
    finally:
        await store.close()
        await engine.dispose()


async def test_correction_supersedes_only_matching_normalized_preference_key(
    tmp_path: Path,
) -> None:
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        drink = claim_write(
            "drink",
            key="preference:drink",
            value="tea",
            evidence_class="explicit",
            guild_id="guild-1",
            channel_id="channel-1",
        )
        game = claim_write(
            "game",
            key="preference:game",
            value="Hades",
            evidence_class="explicit",
            guild_id="guild-1",
            channel_id="channel-1",
            observed_at=NOW + timedelta(minutes=1),
        )
        await store.add_evidence(
            drink, evidence_write("source-drink", guild_id="guild-1", channel_id="channel-1")
        )
        await store.activate_claim("drink", confirmed_at=NOW)
        await store.add_evidence(
            game,
            evidence_write(
                "source-game",
                guild_id="guild-1",
                channel_id="channel-1",
                observed_at=NOW + timedelta(minutes=1),
            ),
        )
        await store.activate_claim("game", confirmed_at=NOW + timedelta(minutes=1))

        await service.observe_turn(
            observation("102", "Actually, I prefer chamomile instead of tea")
        )
        recalled = await service.recall(envelope("turn-after-correction"))

        history = await store.claims_for_subject("user-1")
        states = {(item.key, item.value): item.state for item in history}
        assert states[("preference:drink", "tea")] == "superseded"
        assert states[("preference:drink", "Chamomile")] == "active"
        assert states[("preference:game", "Hades")] == "active"
        assert set(recalled.text.split(" | ")) == {"Chamomile", "Hades"}
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
