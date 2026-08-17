"""Complete and atomic persistence for relationship consolidation."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from tests.persistence.conversations.relationship_memory_test_support import (
    NOW,
    claim,
    evidence,
    inspection_factory,
    policy,
    profile,
    repository,
)

from mika.persistence.conversations.relationship_models import (
    StoredClaim,
    StoredClaimEvidence,
)
from mika.persistence.conversations.relationship_records import ClaimTransitionRecord


async def test_consolidation_reads_include_newest_candidate_after_one_thousand_rows(
    tmp_path: Path,
) -> None:
    """Internal consolidation reads must never silently truncate newer evidence."""
    memory, engine = await repository(tmp_path / "memory.db")
    try:
        await memory.write_policy_version(policy())
        async with inspection_factory(engine)() as inspection:
            for index in range(1001):
                observed_at = NOW + timedelta(seconds=index)
                claim_id = f"claim-{index:04d}"
                inspection.add(
                    StoredClaim(
                        claim_id=claim_id,
                        subject_user_id="user-1",
                        visibility_kind="guild",
                        guild_id="guild-1",
                        channel_id="channel-1",
                        kind="preference",
                        key=f"preference:{index:04d}",
                        value=f"value-{index:04d}",
                        evidence_class="inference",
                        confidence=0.5,
                        state="candidate",
                        predecessor_claim_id=None,
                        first_observed_at=observed_at,
                        last_observed_at=observed_at,
                        last_confirmed_at=None,
                    )
                )
                inspection.add(
                    StoredClaimEvidence(
                        claim_id=claim_id,
                        source_kind="discord",
                        source_id=f"source-{index:04d}",
                        source_message_id=str(index + 1),
                        source_timestamp=observed_at,
                        visibility_kind="guild",
                        guild_id="guild-1",
                        channel_id="channel-1",
                        policy_version_id="policy-1",
                    )
                )
            await inspection.commit()

        claims = await memory.claims_for_subject("user-1")
        evidence = await memory.evidence_for_claims([item.claim_id for item in claims])

        assert len(claims) == 1001
        assert claims[-1].claim_id == "claim-1000"
        assert evidence[-1].claim_id == "claim-1000"
        assert evidence[-1].policy_version_id == "policy-1"
    finally:
        await memory.close()
        await engine.dispose()


async def test_profile_publication_commits_lifecycle_visibility_together(
    tmp_path: Path,
) -> None:
    """Retrieval cannot observe a claim that the published profile demoted."""
    memory, engine = await repository(tmp_path / "memory.db")
    try:
        await memory.write_policy_version(policy())
        await memory.add_evidence(claim("promoted"), evidence("source-promoted"))
        await memory.add_evidence(claim("expired"), evidence("source-expired"))
        await memory.add_evidence(claim("disputed"), evidence("source-disputed"))
        await memory.activate_claim("disputed", confirmed_at=NOW)
        await memory.add_evidence(claim("superseded"), evidence("source-superseded"))
        await memory.activate_claim("superseded", confirmed_at=NOW)

        await memory.publish_consolidation(
            profile("profile-1", "Interests: favorite_game: Hades"),
            (
                ClaimTransitionRecord("promoted", "candidate", "active", NOW),
                ClaimTransitionRecord("expired", "candidate", "expired", NOW),
                ClaimTransitionRecord("disputed", "active", "disputed", NOW),
                ClaimTransitionRecord("superseded", "active", "superseded", NOW),
            ),
        )

        stored_claims = [
            await memory.claim(claim_id)
            for claim_id in ("promoted", "expired", "disputed", "superseded")
        ]
        visible = await memory.claims_for_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )
        active = await memory.active_profile("user-1")
        assert all(item is not None for item in stored_claims)
        assert {item.claim_id: item.state for item in stored_claims if item is not None} == {
            "promoted": "active",
            "expired": "expired",
            "disputed": "disputed",
            "superseded": "superseded",
        }
        assert [item.claim_id for item in visible] == ["promoted"]
        assert active is not None and active.policy_version_id == "policy-1"
    finally:
        await memory.close()
        await engine.dispose()


async def test_failed_profile_publication_rolls_back_lifecycle_transitions(
    tmp_path: Path,
) -> None:
    """A profile conflict cannot expose claim mutations from its failed transaction."""
    memory, engine = await repository(tmp_path / "memory.db")
    try:
        await memory.write_policy_version(policy())
        await memory.add_evidence(claim("candidate"), evidence("source-candidate"))
        original = profile("profile-1", "original overview")
        await memory.write_profile_version(original)

        with pytest.raises(ValueError, match="profile version already exists"):
            await memory.publish_consolidation(
                replace(original, overview_text="mutated overview"),
                (ClaimTransitionRecord("candidate", "candidate", "active", NOW),),
            )

        candidate = await memory.claim("candidate")
        assert candidate is not None and candidate.state == "candidate"
        assert await memory.active_profile("user-1") == original
    finally:
        await memory.close()
        await engine.dispose()
