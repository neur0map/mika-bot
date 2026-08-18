"""Durable evidence-backed relationship memory and archive cursors."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from tests.persistence.conversations.relationship_memory_test_support import (
    NOW,
)
from tests.persistence.conversations.relationship_memory_test_support import (
    claim as _claim,
)
from tests.persistence.conversations.relationship_memory_test_support import (
    create_archive as _create_archive,
)
from tests.persistence.conversations.relationship_memory_test_support import (
    evidence as _evidence,
)
from tests.persistence.conversations.relationship_memory_test_support import (
    inspection_factory as _inspection_factory,
)
from tests.persistence.conversations.relationship_memory_test_support import (
    policy as _policy,
)
from tests.persistence.conversations.relationship_memory_test_support import (
    profile as _profile,
)
from tests.persistence.conversations.relationship_memory_test_support import (
    recall_event as _recall_event,
)
from tests.persistence.conversations.relationship_memory_test_support import (
    repository as _repository,
)

from mika.persistence.conversations.archive_reader import ArchiveReader
from mika.persistence.conversations.relationship_models import (
    StoredClaimEvidence,
    StoredConsolidationCadence,
    StoredProfileScope,
    StoredProfileVersion,
    StoredRecallEvent,
    StoredRecallFeedback,
    StoredRecallFeedbackClaim,
)
from mika.persistence.conversations.relationship_records import (
    ArchiveCursor,
    ArchiveSourceRecord,
    ProfileClaimLinkRecord,
    RecallEventWrite,
    RecallFeedbackWrite,
)
from mika.persistence.conversations.social_models import UserFact


async def test_duplicate_source_does_not_inflate_observation_count(tmp_path: Path) -> None:
    repository, engine = await _repository(tmp_path / "memory.db")
    try:
        await repository.write_policy_version(_policy())
        await repository.add_evidence(_claim("claim-1"), _evidence("source-1"))
        await repository.add_evidence(_claim("claim-1"), _evidence("source-1"))
        await repository.add_evidence(
            _claim("claim-1"),
            _evidence("source-2", source_message_id="message-2"),
        )
        await repository.activate_claim("claim-1", confirmed_at=NOW + timedelta(minutes=1))

        claims = await repository.claims_for_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-9"
        )

        assert len(claims) == 1
        assert claims[0].observation_count == 2
        assert claims[0].source_message_ids == ("message-2", "source-1")
        assert claims[0].state == "active"
        assert claims[0].last_confirmed_at == NOW + timedelta(minutes=1)
    finally:
        await repository.close()
        await engine.dispose()


async def test_correction_supersession_is_atomic_and_preserves_history(tmp_path: Path) -> None:
    repository, engine = await _repository(tmp_path / "memory.db")
    try:
        await repository.write_policy_version(_policy())
        await repository.add_evidence(_claim("old"), _evidence("message-1"))
        await repository.activate_claim("old", confirmed_at=NOW)

        replacement = _claim(
            "new",
            value="Celeste",
            evidence_class="correction",
            state="active",
            predecessor_claim_id="old",
        )
        corrected = await repository.supersede_claim(
            "old", replacement, _evidence("message-2"), superseded_at=NOW + timedelta(hours=1)
        )

        assert corrected.claim_id == "new"
        assert corrected.predecessor_claim_id == "old"
        old = await repository.claim("old")
        assert old is not None
        assert old.state == "superseded"

        with pytest.raises(ValueError, match="replacement claim already exists"):
            await repository.supersede_claim(
                "new",
                replacement,
                _evidence("message-3"),
                superseded_at=NOW + timedelta(hours=2),
            )
        still_active = await repository.claim("new")
        assert still_active is not None
        assert still_active.state == "active"
    finally:
        await repository.close()
        await engine.dispose()


async def test_profile_and_policy_versions_are_immutable_with_atomic_heads(tmp_path: Path) -> None:
    repository, engine = await _repository(tmp_path / "memory.db")
    try:
        await repository.write_policy_version(_policy())
        await repository.write_policy_version(_policy("policy-2"))
        assert (await repository.active_policy_version()) == _policy("policy-2")
        await repository.add_evidence(_claim("claim-1"), _evidence("source-1"))
        await repository.activate_claim("claim-1", confirmed_at=NOW)
        links = (ProfileClaimLinkRecord("claim-1", "interests", 0),)
        first = replace(_profile("profile-1", "first overview"), claim_links=links)
        second = replace(_profile("profile-2", "second overview"), claim_links=links)

        await repository.write_profile_version(first)
        await repository.write_profile_version(second)
        assert (await repository._legacy_active_profile("user-1")) == second

        with pytest.raises(ValueError, match="profile version already exists"):
            await repository.write_profile_version(replace(first, overview_text="mutated overview"))
        assert (await repository._legacy_active_profile("user-1")) == second

        with pytest.raises(ValueError, match="policy version already exists"):
            await repository.write_policy_version(_policy())
        assert (await repository.active_policy_version()) == _policy("policy-2")

        async with _inspection_factory(engine)() as inspection:
            versions = list(
                (
                    await inspection.execute(
                        select(StoredProfileVersion).order_by(
                            StoredProfileVersion.profile_version_id
                        )
                    )
                ).scalars()
            )
        assert [(item.profile_version_id, item.overview_text) for item in versions] == [
            ("profile-1", "first overview"),
            ("profile-2", "second overview"),
        ]
    finally:
        await repository.close()
        await engine.dispose()


async def test_archive_cursor_uses_compound_monotonic_order(tmp_path: Path) -> None:
    repository, engine = await _repository(tmp_path / "memory.db")
    try:
        await repository.write_policy_version(_policy())
        first = ArchiveCursor("weekly", NOW, "100", "policy-1", NOW)
        second = ArchiveCursor("weekly", NOW, "101", "policy-1", NOW + timedelta(minutes=1))
        stale = ArchiveCursor(
            "weekly", NOW - timedelta(seconds=1), "999", "policy-1", NOW + timedelta(minutes=2)
        )

        await repository.advance_cursor(first)
        await repository.advance_cursor(second)
        await repository.advance_cursor(stale)

        assert await repository.cursor("weekly") == second
    finally:
        await repository.close()
        await engine.dispose()


async def test_claim_recall_is_scoped_before_returning_rows(tmp_path: Path) -> None:
    repository, engine = await _repository(tmp_path / "memory.db")
    try:
        await repository.write_policy_version(_policy())
        writes = (
            (
                _claim("global", visibility_kind="global_explicit", guild_id=None),
                _evidence(
                    "global-source",
                    visibility_kind="global_explicit",
                    guild_id=None,
                    channel_id=None,
                ),
            ),
            (_claim("guild"), _evidence("guild-source")),
            (
                _claim("channel", visibility_kind="channel", channel_id="channel-1"),
                _evidence("channel-source", visibility_kind="channel"),
            ),
            (
                _claim(
                    "dm",
                    visibility_kind="direct_message",
                    guild_id=None,
                    channel_id="dm-1",
                ),
                _evidence(
                    "dm-source",
                    visibility_kind="direct_message",
                    guild_id=None,
                    channel_id="dm-1",
                ),
            ),
            (_claim("other-user", user_id="user-2"), _evidence("other-source")),
        )
        for claim, evidence in writes:
            await repository.add_evidence(claim, evidence)
            await repository.activate_claim(claim.claim_id, confirmed_at=NOW)

        public = await repository.claims_for_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )
        other_channel = await repository.claims_for_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-2"
        )
        dm = await repository.claims_for_user(
            "user-1", visibility_kind="direct_message", guild_id=None, channel_id="dm-1"
        )

        assert {claim.claim_id for claim in public} == {"global", "guild", "channel"}
        assert {claim.claim_id for claim in other_channel} == {"global", "guild"}
        assert {claim.claim_id for claim in dm} == {"global", "dm"}
    finally:
        await repository.close()
        await engine.dispose()


async def test_claim_history_and_evidence_reads_include_candidate_lifecycle(tmp_path: Path) -> None:
    repository, engine = await _repository(tmp_path / "memory.db")
    try:
        await repository.write_policy_version(_policy())
        await repository.add_evidence(_claim("candidate"), _evidence("message-1"))
        await repository.add_evidence(_claim("candidate"), _evidence("message-2"))

        claims = await repository.claims_for_subject("user-1")
        evidence = await repository.evidence_for_claims(["candidate"])

        assert [(item.claim_id, item.state, item.observation_count) for item in claims] == [
            ("candidate", "candidate", 2)
        ]
        assert [item.source_message_id for item in evidence] == ["message-1", "message-2"]
        assert all(item.claim_id == "candidate" for item in evidence)
        assert all(item.policy_version_id == "policy-1" for item in evidence)
    finally:
        await repository.close()
        await engine.dispose()


async def test_recall_feedback_is_idempotent_and_cannot_mutate_claim_truth(tmp_path: Path) -> None:
    repository, engine = await _repository(tmp_path / "memory.db")
    try:
        await repository.write_policy_version(_policy())
        await repository.add_evidence(_claim("claim-1"), _evidence("source-1"))
        await repository.activate_claim("claim-1", confirmed_at=NOW)
        before = await repository.claim("claim-1")
        assert before is not None

        await repository.record_recall(_recall_event())
        feedback = RecallFeedbackWrite(
            feedback_id="feedback-1",
            recall_event_id="recall-1",
            outcome="positive",
            selected_claim_ids=("claim-1",),
            created_at=NOW + timedelta(minutes=1),
        )
        await repository.record_recall_feedback(feedback)
        await repository.record_recall_feedback(feedback)

        after = await repository.claim("claim-1")
        assert after is not None
        assert (
            after.value,
            after.evidence_class,
            after.confidence,
            after.state,
            after.predecessor_claim_id,
        ) == (
            before.value,
            before.evidence_class,
            before.confidence,
            before.state,
            before.predecessor_claim_id,
        )
        async with _inspection_factory(engine)() as inspection:
            feedback_count = await inspection.scalar(select(func.count(StoredRecallFeedback.id)))
            link_count = await inspection.scalar(
                select(func.count()).select_from(StoredRecallFeedbackClaim)
            )
        assert feedback_count == 1
        assert link_count == 1

        conflicting = RecallFeedbackWrite(
            feedback_id="feedback-1",
            recall_event_id="recall-1",
            outcome="negative",
            selected_claim_ids=("claim-1",),
            created_at=NOW + timedelta(minutes=1),
        )
        with pytest.raises(ValueError, match="feedback id is already bound"):
            await repository.record_recall_feedback(conflicting)
    finally:
        await repository.close()
        await engine.dispose()


async def test_recall_trace_stores_metadata_without_transcript_text(tmp_path: Path) -> None:
    repository, engine = await _repository(tmp_path / "memory.db")
    try:
        await repository.write_policy_version(_policy())
        event = RecallEventWrite(
            recall_event_id="recall-1",
            subject_user_id="user-1",
            visibility_kind="guild",
            guild_id="guild-1",
            channel_id="channel-1",
            query_hash="sha256:only-a-hash",
            relation_label="follow_up",
            candidate_ids=("claim-1", "claim-2"),
            selected_claim_ids=("claim-1",),
            selected_tiers={"claim-1": "index"},
            rejection_reasons={"claim-2": "scope"},
            estimated_token_cost=8,
            latency_ms=1.25,
            retrieval_version="retrieval-v1",
            policy_version_id="policy-1",
            created_at=NOW,
        )
        await repository.record_recall(event)

        async with _inspection_factory(engine)() as inspection:
            stored = (
                await inspection.execute(
                    select(StoredRecallEvent).where(StoredRecallEvent.recall_event_id == "recall-1")
                )
            ).scalar_one()
        assert json.loads(stored.candidate_ids_json) == ["claim-1", "claim-2"]
        assert json.loads(stored.selected_tiers_json) == {"claim-1": "index"}
        assert stored.policy_version_id == "policy-1"
        assert "content" not in StoredRecallEvent.__table__.columns
        assert "query_text" not in StoredRecallEvent.__table__.columns
        assert "content" not in StoredClaimEvidence.__table__.columns
    finally:
        await repository.close()
        await engine.dispose()


async def test_deleting_user_memory_removes_all_derived_rows_only(tmp_path: Path) -> None:
    repository, engine = await _repository(tmp_path / "memory.db")
    try:
        await repository.write_policy_version(_policy())
        await repository.add_evidence(_claim("claim-1"), _evidence("source-1"))
        await repository.activate_claim("claim-1", confirmed_at=NOW)
        await repository.write_profile_version(
            replace(
                _profile("profile-1", "overview"),
                claim_links=(ProfileClaimLinkRecord("claim-1", "interests", 0),),
                visibility_kind="guild",
                guild_id="guild-1",
                channel_id="channel-1",
            )
        )
        await repository.record_scoped_consolidated_at(
            "user-1",
            NOW,
            visibility_kind="guild",
            guild_id="guild-1",
            channel_id="channel-1",
        )
        await repository.advance_cursor(ArchiveCursor("weekly", NOW, "1", "policy-1", NOW))
        await repository.record_recall(_recall_event())
        await repository.record_recall_feedback(
            RecallFeedbackWrite("feedback-1", "recall-1", "positive", ("claim-1",), NOW)
        )
        async with _inspection_factory(engine)() as inspection:
            inspection.add(
                UserFact(
                    user_id="user-1",
                    fact_key="legacy",
                    fact_value="preserve",
                    source_message_id="missing",
                )
            )
            await inspection.commit()

        await repository.delete_user_memory("user-1")

        assert await repository.claim("claim-1") is None
        assert await repository._legacy_active_profile("user-1") is None
        async with _inspection_factory(engine)() as inspection:
            assert (
                await inspection.scalar(select(func.count(StoredRecallEvent.recall_event_id))) == 0
            )
            assert await inspection.scalar(select(func.count(StoredRecallFeedback.id))) == 0
            assert (
                await inspection.scalar(select(func.count(StoredProfileScope.profile_version_id)))
                == 0
            )
            assert (
                await inspection.scalar(
                    select(func.count()).select_from(StoredConsolidationCadence)
                )
                == 0
            )
            assert (
                await inspection.scalar(select(func.count()).select_from(StoredRecallFeedbackClaim))
                == 0
            )
            assert await inspection.scalar(select(func.count(UserFact.id))) == 1
        assert await repository.active_policy_version() == _policy()
        assert await repository.cursor("weekly") is not None
    finally:
        await repository.close()
        await engine.dispose()


async def test_legacy_migration_requires_resolved_scoped_archive_source(tmp_path: Path) -> None:
    repository, engine = await _repository(tmp_path / "memory.db")
    try:
        await repository.write_policy_version(_policy())
        async with _inspection_factory(engine)() as inspection:
            inspection.add_all(
                [
                    UserFact(
                        user_id="user-1",
                        fact_key="favorite_game",
                        fact_value="Hades",
                        source_message_id="100",
                    ),
                    UserFact(
                        user_id="user-1",
                        fact_key="home_city",
                        fact_value="unknown scope",
                        source_message_id="missing",
                    ),
                ]
            )
            await inspection.commit()
        source = ArchiveSourceRecord(
            source_kind="shared_archive",
            source_id="archive-row-1",
            discord_message_id="100",
            author_id="user-1",
            author_name="Ada",
            text="I like Hades",
            archive_created_at=NOW,
            visibility_kind="channel",
            guild_id="guild-1",
            channel_id="channel-private",
        )

        assert (
            await repository.migrate_resolved_legacy_facts(
                (source,), policy_version_id="policy-1", migrated_at=NOW
            )
            == 1
        )

        visible = await repository.claims_for_user(
            "user-1",
            visibility_kind="guild",
            guild_id="guild-1",
            channel_id="channel-private",
        )
        hidden = await repository.claims_for_user(
            "user-1",
            visibility_kind="guild",
            guild_id="guild-1",
            channel_id="channel-public",
        )
        assert [(claim.key, claim.value) for claim in visible] == [("favorite_game", "Hades")]
        assert hidden == []
        async with _inspection_factory(engine)() as inspection:
            evidence = (await inspection.execute(select(StoredClaimEvidence))).scalar_one()
        assert (
            evidence.source_kind,
            evidence.source_id,
            evidence.source_message_id,
            evidence.source_timestamp,
            evidence.visibility_kind,
            evidence.guild_id,
            evidence.channel_id,
            evidence.policy_version_id,
        ) == (
            "shared_archive",
            "archive-row-1",
            "100",
            NOW,
            "channel",
            "guild-1",
            "channel-private",
            "policy-1",
        )
    finally:
        await repository.close()
        await engine.dispose()


def test_archive_reader_is_read_only_validated_and_compound_ordered(tmp_path: Path) -> None:
    path = tmp_path / "archive.db"
    _create_archive(path)
    before = hashlib.sha256(path.read_bytes()).digest()
    reader = ArchiveReader(path, source_name="weekly")

    first_page = reader.iter_after(None, limit=2)
    cursor = ArchiveCursor(
        source_name="weekly",
        archive_created_at=first_page[-1].archive_created_at,
        discord_message_id=first_page[-1].discord_message_id,
        policy_version_id="policy-1",
        updated_at=NOW,
    )
    second_page = reader.iter_after(cursor, limit=10)

    assert [row.discord_message_id for row in first_page] == ["100", "101"]
    assert [row.discord_message_id for row in second_page] == ["102"]
    assert first_page[0].archive_created_at == NOW
    assert first_page[0].visibility_kind == "channel"
    assert second_page[0].visibility_kind == "direct_message"
    assert hashlib.sha256(path.read_bytes()).digest() == before

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM messages").fetchone() == (5,)
