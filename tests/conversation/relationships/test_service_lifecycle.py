"""Relationship-service lifecycle publication regressions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

from tests.conversation.relationships.test_service import (
    Classifier,
    Extractor,
    Retriever,
    claim_write,
    evidence_write,
    observation,
    service_for,
)
from tests.persistence.conversations.relationship_memory_test_support import (
    inspection_factory,
    policy,
)

from mika.conversation.relationships.activation import ActivationPolicy
from mika.conversation.relationships.consolidation import (
    ConsolidationResult,
    RelationshipConsolidator,
)
from mika.conversation.relationships.contracts import RelationshipClaim
from mika.conversation.relationships.extraction import EvidenceProposal
from mika.conversation.relationships.profile import RelationshipProfile
from mika.conversation.relationships.service import RelationshipMemoryService
from mika.persistence.conversations.relationship_models import (
    StoredClaim,
    StoredClaimEvidence,
    StoredProfileHead,
    StoredProfileVersion,
)
from mika.persistence.conversations.relationship_records import ProfileClaimLinkRecord

NOW = observation("fixture").created_at


class LossyConsolidator(RelationshipConsolidator):
    """Simulate a consolidation defect that drops a protected anchor."""

    def consolidate(
        self,
        claims: Sequence[RelationshipClaim],
        evidence_by_key: Mapping[str, Sequence[EvidenceProposal]] | None = None,
        *,
        evidence_by_claim_id: Mapping[str, Sequence[EvidenceProposal]] | None = None,
        predecessor: RelationshipProfile | None = None,
        now: datetime,
    ) -> ConsolidationResult:
        return super().consolidate(
            tuple(item for item in claims if item.claim_id != "anchor"),
            evidence_by_key,
            evidence_by_claim_id=evidence_by_claim_id,
            predecessor=predecessor,
            now=now,
        )


class DisputingOriginalConsolidator(RelationshipConsolidator):
    """Demote one duplicate while leaving its replacement prompt-active."""

    def consolidate(
        self,
        claims: Sequence[RelationshipClaim],
        evidence_by_key: Mapping[str, Sequence[EvidenceProposal]] | None = None,
        *,
        evidence_by_claim_id: Mapping[str, Sequence[EvidenceProposal]] | None = None,
        predecessor: RelationshipProfile | None = None,
        now: datetime,
    ) -> ConsolidationResult:
        updated = tuple(
            replace(claim, state="disputed") if claim.claim_id == "original" else claim
            for claim in claims
        )
        return super().consolidate(
            updated,
            evidence_by_key,
            evidence_by_claim_id=evidence_by_claim_id,
            predecessor=predecessor,
            now=now,
        )


async def test_correction_discovery_includes_newest_claim_after_one_thousand_rows(
    tmp_path: Path,
) -> None:
    """A recent correction target cannot disappear behind older history."""
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        async with inspection_factory(engine)() as inspection:
            for index in range(1001):
                newest = index == 1000
                observed_at = NOW + timedelta(seconds=index)
                claim_id = "newest-drink" if newest else f"older-{index:04d}"
                inspection.add(
                    StoredClaim(
                        claim_id=claim_id,
                        subject_user_id="user-1",
                        visibility_kind="guild",
                        guild_id="guild-1",
                        channel_id="channel-1",
                        kind="preference",
                        key="preference:drink" if newest else f"preference:{index:04d}",
                        value="Tea" if newest else f"value-{index:04d}",
                        evidence_class="explicit" if newest else "inference",
                        confidence=0.95 if newest else 0.5,
                        state="active" if newest else "candidate",
                        predecessor_claim_id=None,
                        first_observed_at=observed_at,
                        last_observed_at=observed_at,
                        last_confirmed_at=observed_at if newest else None,
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

        await service.observe_turn(
            observation("2002", "Actually, I prefer chamomile instead of tea")
        )

        history = await store.claims_for_subject("user-1")
        correction = next(item for item in history if item.value == "Chamomile")
        predecessor = await store.claim("newest-drink")
        assert correction.predecessor_claim_id == "newest-drink"
        assert predecessor is not None and predecessor.state == "superseded"
    finally:
        await store.close()
        await engine.dispose()


async def test_consolidation_rejects_loss_of_active_predecessor_anchor(tmp_path: Path) -> None:
    """Service publication must preserve protected entries from the active profile."""
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        anchor = replace(
            claim_write(
                "anchor",
                key="shared:trip",
                value="Berlin",
                evidence_class="explicit",
                guild_id="guild-1",
                channel_id="channel-1",
            ),
            kind="anchor",
        )
        await store.add_evidence(
            anchor,
            evidence_write("anchor-source", guild_id="guild-1", channel_id="channel-1"),
        )
        await store.activate_claim("anchor", confirmed_at=NOW)
        initial = await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )
        assert initial.profile_version_id is not None

        lossy_service = RelationshipMemoryService(
            repository=store,
            extractor=Extractor(),
            activation_policy=ActivationPolicy(),
            classifier=Classifier(),
            retriever=Retriever(store),
            consolidator=LossyConsolidator(),
            clock=lambda: NOW + timedelta(minutes=5),
        )
        result = await lossy_service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )

        active = (await store.active_profiles_for_subject("user-1"))[0]
        assert result.rejected is True
        assert result.profile_changed is False
        assert active is not None
        assert active.profile_version_id == initial.profile_version_id
        assert "Berlin" in active.overview_text
    finally:
        await store.close()
        await engine.dispose()


async def test_consolidation_persists_expired_candidate_lifecycle(tmp_path: Path) -> None:
    """A consolidation-produced expiry must reach durable claim retrieval state."""
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        observed_at = NOW - timedelta(days=31)
        stale = claim_write(
            "stale-inference",
            key="preference:juice",
            value="Juice",
            evidence_class="inference",
            guild_id="guild-1",
            channel_id="channel-1",
            observed_at=observed_at,
        )
        await store.add_evidence(
            stale,
            evidence_write(
                "stale-source",
                guild_id="guild-1",
                channel_id="channel-1",
                observed_at=observed_at,
            ),
        )

        result = await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )

        stored = await store.claim("stale-inference")
        assert result.policy_version_id == "policy-1"
        assert stored is not None and stored.state == "expired"
    finally:
        await store.close()
        await engine.dispose()


async def test_unchanged_profile_is_republished_under_effective_policy(tmp_path: Path) -> None:
    """An active profile must remain attributable to the policy that produced it."""
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        await service.observe_turn(observation("100"))
        await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )
        await store.write_policy_version(policy("policy-2"))

        result = await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )

        active = (await store.active_profiles_for_subject("user-1"))[0]
        assert result.profile_changed is True
        assert result.policy_version_id == "policy-2"
        assert active is not None and active.policy_version_id == "policy-2"
    finally:
        await store.close()
        await engine.dispose()


async def test_predecessor_profile_round_trips_delimiter_values_losslessly(tmp_path: Path) -> None:
    """Display delimiters inside values cannot corrupt predecessor reconstruction."""
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        preference = claim_write(
            "delimiter-value",
            key="preference:drink",
            value="Tea; coffee",
            evidence_class="explicit",
            guild_id="guild-1",
            channel_id="channel-1",
        )
        await store.add_evidence(
            preference,
            evidence_write("delimiter-source", guild_id="guild-1", channel_id="channel-1"),
        )
        await store.activate_claim("delimiter-value", confirmed_at=NOW)

        first = await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )
        second = await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )

        active = (await store.active_profiles_for_subject("user-1"))[0]
        assert first.profile_changed is True
        assert second.profile_changed is False
        assert active is not None and "Tea; coffee" in active.overview_text
    finally:
        await store.close()
        await engine.dispose()


async def test_same_rendered_profile_republishes_changed_claim_membership(tmp_path: Path) -> None:
    """Duplicate support updates links so one member can later be demoted safely."""
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        original = claim_write(
            "original",
            key="preference:drink",
            value="Tea",
            evidence_class="explicit",
            guild_id="guild-1",
            channel_id="channel-1",
        )
        replacement = replace(original, claim_id="replacement")
        await store.add_evidence(
            original,
            evidence_write("original-source", guild_id="guild-1", channel_id="channel-1"),
        )
        await store.activate_claim("original", confirmed_at=NOW)
        await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )
        await store.add_evidence(
            replacement,
            evidence_write("replacement-source", guild_id="guild-1", channel_id="channel-1"),
        )
        await store.activate_claim("replacement", confirmed_at=NOW + timedelta(minutes=1))

        expanded = await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )
        expanded_profile = (await store.active_profiles_for_subject("user-1"))[0]

        disputing_service = RelationshipMemoryService(
            repository=store,
            extractor=Extractor(),
            activation_policy=ActivationPolicy(),
            classifier=Classifier(),
            retriever=Retriever(store),
            consolidator=DisputingOriginalConsolidator(),
            clock=lambda: NOW + timedelta(minutes=5),
        )
        await disputing_service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )

        active = (await store.active_profiles_for_subject("user-1"))[0]
        original_record = await store.claim("original")
        replacement_record = await store.claim("replacement")
        assert expanded.profile_changed is True
        assert expanded_profile is not None
        assert {link.claim_id for link in expanded_profile.claim_links} == {
            "original",
            "replacement",
        }
        assert original_record is not None and original_record.state == "disputed"
        assert replacement_record is not None and replacement_record.state == "active"
        assert active is not None
        assert [link.claim_id for link in active.claim_links] == ["replacement"]
    finally:
        await store.close()
        await engine.dispose()


async def test_legacy_unlinked_profile_is_republished_with_canonical_links(tmp_path: Path) -> None:
    """Legacy rendered content upgrades from complete claims without delimiter parsing."""
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        preference = claim_write(
            "legacy-claim",
            key="preference:drink",
            value="Tea; coffee",
            evidence_class="explicit",
            guild_id="guild-1",
            channel_id="channel-1",
        )
        await store.add_evidence(
            preference,
            evidence_write("legacy-source", guild_id="guild-1", channel_id="channel-1"),
        )
        await store.activate_claim("legacy-claim", confirmed_at=NOW)
        async with inspection_factory(engine)() as inspection:
            inspection.add(
                StoredProfileVersion(
                    profile_version_id="legacy-profile",
                    subject_user_id="user-1",
                    index_text="preference:drink: Tea; coffee",
                    overview_text="Interests: preference:drink: Tea; coffee",
                    schema_version="relationship-profile-v1",
                    generator_version="deterministic-v1",
                    policy_version_id="policy-1",
                    created_at=NOW + timedelta(minutes=1),
                )
            )
            inspection.add(
                StoredProfileHead(subject_user_id="user-1", profile_version_id="legacy-profile")
            )
            await inspection.commit()

        result = await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="guild-1", channel_id="channel-1"
        )

        active = (await store.active_profiles_for_subject("user-1"))[0]
        assert result.profile_changed is True
        assert active is not None and active.profile_version_id != "legacy-profile"
        assert active.claim_links == (ProfileClaimLinkRecord("legacy-claim", "interests", 0),)
        assert active.overview_text == "Interests: preference:drink: Tea; coffee"
    finally:
        await store.close()
        await engine.dispose()
