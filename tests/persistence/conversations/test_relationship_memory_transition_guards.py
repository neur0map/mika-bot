"""Transition guards for relationship-memory corrections."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from tests.persistence.conversations.relationship_memory_test_support import (
    NOW,
    claim,
    evidence,
    policy,
    repository,
)

from mika.persistence.conversations.relationship_memory import RelationshipMemoryRepository


async def test_correction_candidates_validate_predecessor_identity_and_scope(
    tmp_path: Path,
) -> None:
    memory, engine = await repository(tmp_path / "memory.db")
    try:
        await memory.write_policy_version(policy())
        private = claim("private", visibility_kind="channel", channel_id="private-channel")
        await memory.add_evidence(
            private,
            evidence("source-1", visibility_kind="channel", channel_id="private-channel"),
        )
        await memory.activate_claim("private", confirmed_at=NOW)
        other_user = claim(
            "other-user",
            user_id="user-2",
            value="Celeste",
            evidence_class="correction",
            visibility_kind="guild",
            predecessor_claim_id="private",
        )
        public = replace(other_user, claim_id="public", subject_user_id="user-1")

        with pytest.raises(ValueError, match="replacement subject and key must match"):
            await memory.add_evidence(other_user, evidence("source-2"))
        with pytest.raises(ValueError, match="replacement cannot widen predecessor scope"):
            await memory.add_evidence(public, evidence("source-3"))

        assert await memory.claim("other-user") is None
        assert await memory.claim("public") is None
        current = await memory.claim("private")
        assert current is not None and current.state == "active"
    finally:
        await memory.close()
        await engine.dispose()


async def test_activating_correction_supersedes_only_a_current_predecessor(
    tmp_path: Path,
) -> None:
    memory, engine = await repository(tmp_path / "memory.db")
    try:
        await memory.write_policy_version(policy())
        private = claim("private", visibility_kind="channel", channel_id="private-channel")
        await memory.add_evidence(
            private,
            evidence("source-1", visibility_kind="channel", channel_id="private-channel"),
        )
        await memory.activate_claim("private", confirmed_at=NOW)
        first = claim(
            "first",
            value="Celeste",
            evidence_class="correction",
            visibility_kind="channel",
            channel_id="private-channel",
            predecessor_claim_id="private",
        )
        second = replace(first, claim_id="second", value="Dead Cells")
        await memory.add_evidence(
            first,
            evidence("source-2", visibility_kind="channel", channel_id="private-channel"),
        )
        await memory.add_evidence(
            second,
            evidence("source-3", visibility_kind="channel", channel_id="private-channel"),
        )

        activated = await memory.activate_claim("first", confirmed_at=NOW + timedelta(minutes=1))

        assert activated.state == "active"
        predecessor = await memory.claim("private")
        assert predecessor is not None and predecessor.state == "superseded"
        with pytest.raises(ValueError, match="predecessor is not current"):
            await memory.activate_claim("second", confirmed_at=NOW + timedelta(minutes=2))
        rejected = await memory.claim("second")
        assert rejected is not None and rejected.state == "candidate"
    finally:
        await memory.close()
        await engine.dispose()


async def test_concurrent_supersession_has_one_winner_and_one_clean_failure(
    tmp_path: Path,
) -> None:
    setup, engine = await repository(tmp_path / "memory.db")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    first_memory = RelationshipMemoryRepository(factory())
    second_memory = RelationshipMemoryRepository(factory())
    try:
        await setup.write_policy_version(policy())
        await setup.add_evidence(claim("old"), evidence("source-1"))
        await setup.activate_claim("old", confirmed_at=NOW)
        await setup.close()
        assert await first_memory.claim("old") is not None
        assert await second_memory.claim("old") is not None
        start = asyncio.Event()

        async def replace_current(
            memory: RelationshipMemoryRepository,
            claim_id: str,
            source_id: str,
        ) -> object:
            await start.wait()
            replacement = claim(
                claim_id,
                value="Celeste",
                evidence_class="correction",
                state="active",
                predecessor_claim_id="old",
            )
            return await memory.supersede_claim(
                "old", replacement, evidence(source_id), superseded_at=NOW
            )

        first_call = asyncio.create_task(replace_current(first_memory, "new-1", "source-2"))
        second_call = asyncio.create_task(replace_current(second_memory, "new-2", "source-3"))
        start.set()
        outcomes = await asyncio.gather(first_call, second_call, return_exceptions=True)

        failures = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
        successes = [outcome for outcome in outcomes if not isinstance(outcome, BaseException)]
        assert len(successes) == 1, outcomes
        assert len(failures) == 1
        assert isinstance(failures[0], ValueError)
        assert str(failures[0]) == "predecessor is not current"

        inspection = RelationshipMemoryRepository(factory())
        try:
            predecessor = await inspection.claim("old")
            successors = [await inspection.claim("new-1"), await inspection.claim("new-2")]
            assert predecessor is not None and predecessor.state == "superseded"
            assert sum(item is not None and item.state == "active" for item in successors) == 1
            assert sum(item is None for item in successors) == 1
        finally:
            await inspection.close()
    finally:
        await setup.close()
        await first_memory.close()
        await second_memory.close()
        await engine.dispose()
