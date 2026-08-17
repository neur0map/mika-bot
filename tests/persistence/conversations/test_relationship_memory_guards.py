"""Security and integrity guards for relationship-memory persistence."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from tests.persistence.conversations.relationship_memory_test_support import (
    NOW,
    claim,
    evidence,
    policy,
    profile,
    recall_event,
    repository,
)

from mika.persistence.conversations.relationship_records import ArchiveCursor


async def test_private_evidence_cannot_create_a_public_claim(tmp_path: Path) -> None:
    memory, engine = await repository(tmp_path / "memory.db")
    try:
        await memory.write_policy_version(policy())

        with pytest.raises(ValueError, match="claim scope cannot be wider than evidence scope"):
            await memory.add_evidence(
                claim("leak", visibility_kind="guild"),
                evidence("private", visibility_kind="channel", channel_id="private-channel"),
            )

        assert await memory.claim("leak") is None
    finally:
        await memory.close()
        await engine.dispose()


async def test_correction_cannot_promote_private_claim_to_public_scope(tmp_path: Path) -> None:
    memory, engine = await repository(tmp_path / "memory.db")
    try:
        await memory.write_policy_version(policy())
        private = claim("private", visibility_kind="channel", channel_id="private-channel")
        await memory.add_evidence(
            private,
            evidence("source-1", visibility_kind="channel", channel_id="private-channel"),
        )
        await memory.activate_claim("private", confirmed_at=NOW)
        public = claim(
            "public",
            value="Celeste",
            evidence_class="correction",
            state="active",
            visibility_kind="guild",
            predecessor_claim_id="private",
        )

        with pytest.raises(ValueError, match="replacement cannot widen predecessor scope"):
            await memory.supersede_claim(
                "private",
                public,
                evidence("source-2"),
                superseded_at=NOW + timedelta(minutes=1),
            )

        current = await memory.claim("private")
        assert current is not None and current.state == "active"
        assert await memory.claim("public") is None
    finally:
        await memory.close()
        await engine.dispose()


async def test_correction_requires_same_subject_and_key(tmp_path: Path) -> None:
    memory, engine = await repository(tmp_path / "memory.db")
    try:
        await memory.write_policy_version(policy())
        await memory.add_evidence(claim("old"), evidence("source-1"))
        await memory.activate_claim("old", confirmed_at=NOW)
        other_user = claim(
            "other-user",
            user_id="user-2",
            value="Celeste",
            evidence_class="correction",
            predecessor_claim_id="old",
        )
        other_key = replace(
            claim(
                "other-key",
                value="Celeste",
                evidence_class="correction",
                predecessor_claim_id="old",
            ),
            key="favorite_book",
        )

        with pytest.raises(ValueError, match="replacement subject and key must match"):
            await memory.supersede_claim("old", other_user, evidence("source-2"), superseded_at=NOW)
        with pytest.raises(ValueError, match="replacement subject and key must match"):
            await memory.supersede_claim("old", other_key, evidence("source-3"), superseded_at=NOW)

        current = await memory.claim("old")
        assert current is not None and current.state == "active"
    finally:
        await memory.close()
        await engine.dispose()


async def test_superseded_claim_cannot_be_reactivated_or_replaced_twice(tmp_path: Path) -> None:
    memory, engine = await repository(tmp_path / "memory.db")
    try:
        await memory.write_policy_version(policy())
        await memory.add_evidence(claim("old"), evidence("source-1"))
        await memory.activate_claim("old", confirmed_at=NOW)
        replacement = claim(
            "new",
            value="Celeste",
            evidence_class="correction",
            state="active",
            predecessor_claim_id="old",
        )
        await memory.supersede_claim("old", replacement, evidence("source-2"), superseded_at=NOW)

        with pytest.raises(ValueError, match="predecessor is not current"):
            await memory.supersede_claim(
                "old",
                replace(replacement, claim_id="newer"),
                evidence("source-3"),
                superseded_at=NOW,
            )
        with pytest.raises(ValueError, match="cannot activate claim in superseded state"):
            await memory.activate_claim("old", confirmed_at=NOW + timedelta(minutes=1))
    finally:
        await memory.close()
        await engine.dispose()


async def test_cursor_uses_numeric_discord_id_order_and_rejects_invalid_ids(tmp_path: Path) -> None:
    memory, engine = await repository(tmp_path / "memory.db")
    try:
        await memory.write_policy_version(policy())
        first = ArchiveCursor("weekly", NOW, "9", "policy-1", NOW)
        second = ArchiveCursor("weekly", NOW, "10", "policy-1", NOW + timedelta(seconds=1))

        await memory.advance_cursor(first)
        await memory.advance_cursor(second)

        assert await memory.cursor("weekly") == second
        with pytest.raises(ValueError, match="Discord message ID must be a positive integer"):
            await memory.advance_cursor(
                ArchiveCursor("other", NOW, "invalid", "policy-1", NOW + timedelta(seconds=2))
            )
    finally:
        await memory.close()
        await engine.dispose()


async def test_every_derived_write_rejects_a_missing_policy_version(tmp_path: Path) -> None:
    memory, engine = await repository(tmp_path / "memory.db")
    try:
        with pytest.raises(ValueError, match="policy version does not exist"):
            await memory.add_evidence(claim("claim-1"), evidence("source-1"))
        with pytest.raises(ValueError, match="policy version does not exist"):
            await memory.write_profile_version(profile("profile-1", "overview"))
        with pytest.raises(ValueError, match="policy version does not exist"):
            await memory.advance_cursor(ArchiveCursor("weekly", NOW, "1", "policy-1", NOW))
        with pytest.raises(ValueError, match="policy version does not exist"):
            await memory.record_recall(recall_event())

        assert await memory.claim("claim-1") is None
        assert await memory.active_profile("user-1") is None
        assert await memory.cursor("weekly") is None
    finally:
        await memory.close()
        await engine.dispose()


async def test_supersession_rejects_a_missing_policy_without_mutating_claims(
    tmp_path: Path,
) -> None:
    memory, engine = await repository(tmp_path / "memory.db")
    try:
        await memory.write_policy_version(policy())
        await memory.add_evidence(claim("old"), evidence("source-1"))
        await memory.activate_claim("old", confirmed_at=NOW)
        replacement = claim(
            "new",
            value="Celeste",
            evidence_class="correction",
            state="active",
            predecessor_claim_id="old",
        )

        with pytest.raises(ValueError, match="policy version does not exist"):
            await memory.supersede_claim(
                "old",
                replacement,
                replace(evidence("source-2"), policy_version_id="missing"),
                superseded_at=NOW,
            )

        current = await memory.claim("old")
        assert current is not None and current.state == "active"
        assert await memory.claim("new") is None
    finally:
        await memory.close()
        await engine.dispose()


async def test_repository_does_not_expose_its_owned_session(tmp_path: Path) -> None:
    memory, engine = await repository(tmp_path / "memory.db")
    try:
        assert not hasattr(memory, "session")
    finally:
        await memory.close()
        await engine.dispose()


def test_persistence_package_import_does_not_load_conversation_layer() -> None:
    script = (
        "import sys; import mika.persistence.conversations; "
        "print([name for name in sys.modules if name.startswith('mika.conversation')])"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "[]"
