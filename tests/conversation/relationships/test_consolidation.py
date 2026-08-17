"""Deterministic relationship-profile consolidation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mika.conversation.relationships import RelationshipClaim, RelationshipConsolidator
from mika.conversation.relationships.extraction import EvidenceProposal

BASE_TIME = datetime(2026, 8, 17, 10, tzinfo=UTC)


def claim(
    claim_id: str,
    *,
    key: str = "preference:tea",
    value: str = "tea",
    kind: str = "preference",
    evidence_class: str = "explicit",
    confidence: float = 0.8,
    state: str = "active",
    source_ids: tuple[str, ...] = ("message-1",),
    observations: int = 1,
    observed_at: datetime = BASE_TIME,
    predecessor_claim_id: str | None = None,
) -> RelationshipClaim:
    """Build a source-backed claim for profile assertions."""
    return RelationshipClaim(
        claim_id=claim_id,
        subject_user_id="user-1",
        guild_id="guild-1",
        channel_id="channel-1",
        kind=kind,
        key=key,
        value=value,
        evidence_class=evidence_class,  # type: ignore[arg-type]
        confidence=confidence,
        source_message_ids=source_ids,
        observation_count=observations,
        first_observed_at=observed_at,
        last_observed_at=observed_at,
        last_confirmed_at=observed_at if state == "active" else None,
        state=state,  # type: ignore[arg-type]
        predecessor_claim_id=predecessor_claim_id,
    )


def evidence(
    source_id: str,
    observed_at: datetime,
    *,
    key: str = "preference:tea",
    value: str = "tea",
    evidence_class: str = "repeated_behavior",
) -> EvidenceProposal:
    """Build evidence for deterministic promotion tests."""
    return EvidenceProposal(
        kind="preference",
        key=key,
        value=value,
        evidence_class=evidence_class,  # type: ignore[arg-type]
        confidence=0.5,
        source_message_id=source_id,
        source_timestamp=observed_at,
        reason="test",
    )


def test_duplicate_claims_merge_source_support_without_confidence_inflation() -> None:
    """Equivalent claims become one entry while retaining all source identity."""
    result = RelationshipConsolidator().consolidate(
        [
            claim("tea-a", confidence=0.6, source_ids=("message-1",), observations=1),
            claim("tea-b", confidence=0.9, source_ids=("message-2",), observations=1),
        ],
        now=BASE_TIME,
    )

    assert result.profile is not None
    assert len(result.profile.interests) == 1
    assert result.profile.interests[0].claim_ids == ("tea-a", "tea-b")
    assert result.claims[0].confidence == 0.9
    assert result.claims[0].source_message_ids == ("message-1", "message-2")
    assert result.claims[0].observation_count == 2


def test_candidate_promotes_only_from_diverse_supported_observations() -> None:
    """Three source-distinct behavior observations over two days activate a claim."""
    candidate = claim("tea", evidence_class="repeated_behavior", state="candidate")

    result = RelationshipConsolidator().consolidate(
        [candidate],
        evidence_by_key={
            candidate.key: (
                evidence("message-1", BASE_TIME),
                evidence("message-2", BASE_TIME + timedelta(days=1)),
                evidence("message-3", BASE_TIME + timedelta(days=1, hours=1)),
            )
        },
        now=BASE_TIME + timedelta(days=1),
    )

    assert result.claims[0].state == "active"
    assert result.profile is not None
    assert result.profile.interests[0].claim_ids == ("tea",)


def test_temporal_contradictions_remain_visible_without_a_replacement_link() -> None:
    """Conflicting facts stay in the profile until a correction identifies its target."""
    result = RelationshipConsolidator().consolidate(
        [
            claim("old", value="tea", observed_at=BASE_TIME),
            claim("new", value="coffee", observed_at=BASE_TIME + timedelta(days=1)),
        ],
        now=BASE_TIME + timedelta(days=1),
    )

    assert result.profile is not None
    assert [entry.claim_ids for entry in result.profile.interests] == [("old",), ("new",)]
    assert {item.claim_id: item.state for item in result.claims} == {
        "new": "active",
        "old": "active",
    }


def test_correction_replaces_only_its_linked_predecessor() -> None:
    """A correction supersedes its predecessor while preserving that claim in history."""
    result = RelationshipConsolidator().consolidate(
        [
            claim("old", evidence_class="repeated_behavior"),
            claim(
                "corrected",
                value="coffee",
                evidence_class="correction",
                predecessor_claim_id="old",
            ),
        ],
        now=BASE_TIME,
    )

    assert {item.claim_id: item.state for item in result.claims} == {
        "corrected": "active",
        "old": "superseded",
    }
    assert result.profile is not None
    assert result.profile.interests[0].claim_ids == ("corrected",)


def test_stale_weak_inference_expires_without_hiding_durable_facts() -> None:
    """Old unconfirmed inference is excluded while a direct fact remains prompt-visible."""
    result = RelationshipConsolidator().consolidate(
        [
            claim(
                "guess",
                key="preference:juice",
                value="juice",
                evidence_class="inference",
                state="candidate",
                observed_at=BASE_TIME - timedelta(days=31),
            ),
            claim("fact", value="tea"),
        ],
        now=BASE_TIME,
    )

    assert {item.claim_id: item.state for item in result.claims}["guess"] == "expired"
    assert result.profile is not None
    assert result.profile.interests[0].claim_ids == ("fact",)


def test_canonical_rerun_is_a_stable_no_op() -> None:
    """Identical canonical content reuses the predecessor version."""
    consolidator = RelationshipConsolidator()
    first = consolidator.consolidate([claim("tea")], now=BASE_TIME)
    assert first.profile is not None

    rerun = consolidator.consolidate([claim("tea")], predecessor=first.profile, now=BASE_TIME)

    assert rerun.changed is False
    assert rerun.profile is first.profile
    assert rerun.profile.version == 1


def test_lossy_candidate_keeps_predecessor_and_salvages_new_validated_entries() -> None:
    """Protected predecessor entries cannot disappear during a partial consolidation."""
    consolidator = RelationshipConsolidator()
    protected = consolidator.consolidate(
        [claim("correction", evidence_class="correction", key="address:old", value="avoid")],
        now=BASE_TIME,
    )
    assert protected.profile is not None

    result = consolidator.consolidate(
        [claim("new-fact", key="preference:coffee", value="coffee")],
        predecessor=protected.profile,
        now=BASE_TIME + timedelta(days=1),
    )

    assert result.rejected is True
    assert result.rollback_safe is True
    assert result.profile is not None
    assert [entry.claim_ids for entry in result.profile.conflict_repair] == [("correction",)]
    assert [entry.claim_ids for entry in result.profile.interests] == [("new-fact",)]
    assert result.salvaged_claim_ids == ("new-fact",)


def test_superseded_or_expired_predecessor_fact_may_leave_the_overview() -> None:
    """The exact protected predecessor claim is removable only after its lifecycle ends."""
    consolidator = RelationshipConsolidator()
    initial = consolidator.consolidate([claim("fact")], now=BASE_TIME)
    assert initial.profile is not None

    result = consolidator.consolidate(
        [
            claim("fact", state="superseded"),
            claim(
                "replacement",
                value="coffee",
                evidence_class="correction",
                predecessor_claim_id="fact",
            ),
        ],
        predecessor=initial.profile,
        now=BASE_TIME + timedelta(days=1),
    )

    assert result.rejected is False
    assert result.profile is not None
    assert result.profile.interests[0].claim_ids == ("replacement",)
