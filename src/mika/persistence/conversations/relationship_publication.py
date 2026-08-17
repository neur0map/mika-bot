"""Atomic profile and claim-lifecycle publication for relationship consolidation."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from mika.persistence.conversations.relationship_mapping import as_utc
from mika.persistence.conversations.relationship_models import (
    StoredClaim,
    StoredPolicyVersion,
    StoredProfileClaimLink,
    StoredProfileHead,
    StoredProfileVersion,
)
from mika.persistence.conversations.relationship_records import (
    ClaimTransitionRecord,
    ProfileClaimLinkRecord,
    ProfileVersionRecord,
)

_ALLOWED_TRANSITIONS = {
    "candidate": frozenset({"active", "expired", "disputed", "superseded"}),
    "active": frozenset({"expired", "disputed", "superseded"}),
    "disputed": frozenset({"expired", "superseded"}),
}
_PROFILE_LAYERS = frozenset(
    {"posture", "expression", "interests", "care_patterns", "conflict_repair", "anchors"}
)


async def publish_consolidation(
    session: AsyncSession,
    profile: ProfileVersionRecord | None,
    transitions: Sequence[ClaimTransitionRecord],
) -> None:
    """Commit a profile head and its lifecycle transitions as one transaction."""
    try:
        await _stage_transitions(session, profile, transitions)
        if profile is not None:
            await _stage_profile(session, profile)
        await _validate_active_profile(session)
        await session.commit()
    except (SQLAlchemyError, ValueError):
        await session.rollback()
        raise


async def _stage_transitions(
    session: AsyncSession,
    profile: ProfileVersionRecord | None,
    transitions: Sequence[ClaimTransitionRecord],
) -> None:
    seen: set[str] = set()
    subject_user_id = None if profile is None else profile.subject_user_id
    for transition in transitions:
        if transition.claim_id in seen:
            raise ValueError("claim has more than one consolidation transition")
        seen.add(transition.claim_id)
        allowed = _ALLOWED_TRANSITIONS.get(transition.previous_state, frozenset())
        if transition.next_state not in allowed:
            raise ValueError("claim consolidation transition is not allowed")
        stored = await session.scalar(
            select(StoredClaim).where(StoredClaim.claim_id == transition.claim_id).with_for_update()
        )
        if stored is None:
            raise ValueError("claim does not exist")
        if stored.state != transition.previous_state:
            raise ValueError("claim lifecycle changed before consolidation publication")
        if subject_user_id is None:
            subject_user_id = stored.subject_user_id
        elif stored.subject_user_id != subject_user_id:
            raise ValueError("consolidation publication cannot mix subjects")
        stored.state = transition.next_state
        if transition.next_state == "active":
            stored.last_confirmed_at = as_utc(transition.transitioned_at)


async def _stage_profile(session: AsyncSession, record: ProfileVersionRecord) -> None:
    if await session.get(StoredPolicyVersion, record.policy_version_id) is None:
        raise ValueError("policy version does not exist")
    await _validate_links(session, record)
    stored = await session.get(StoredProfileVersion, record.profile_version_id)
    if stored is None:
        session.add(
            StoredProfileVersion(
                profile_version_id=record.profile_version_id,
                subject_user_id=record.subject_user_id,
                index_text=record.index_text,
                overview_text=record.overview_text,
                schema_version=record.schema_version,
                generator_version=record.generator_version,
                policy_version_id=record.policy_version_id,
                created_at=record.created_at,
            )
        )
        session.add_all(
            [
                StoredProfileClaimLink(
                    profile_version_id=record.profile_version_id,
                    claim_id=link.claim_id,
                    layer=link.layer,
                    position=link.position,
                )
                for link in record.claim_links
            ]
        )
        await session.flush()
    else:
        await _validate_existing_profile(session, stored, record)
    head = await session.get(StoredProfileHead, record.subject_user_id)
    if head is None:
        session.add(
            StoredProfileHead(
                subject_user_id=record.subject_user_id,
                profile_version_id=record.profile_version_id,
            )
        )
    else:
        head.profile_version_id = record.profile_version_id


async def _validate_links(session: AsyncSession, record: ProfileVersionRecord) -> None:
    seen: set[str] = set()
    for link in record.claim_links:
        if link.claim_id in seen:
            raise ValueError("profile claim link is duplicated")
        seen.add(link.claim_id)
        if link.layer not in _PROFILE_LAYERS or link.position < 0:
            raise ValueError("profile claim link metadata is invalid")
        claim = await session.get(StoredClaim, link.claim_id)
        if claim is None:
            raise ValueError("profile claim does not exist")
        if claim.subject_user_id != record.subject_user_id:
            raise ValueError("profile claim belongs to a different subject")
        if claim.state != "active":
            raise ValueError("profile can link only active claims")


async def _validate_existing_profile(
    session: AsyncSession,
    stored: StoredProfileVersion,
    record: ProfileVersionRecord,
) -> None:
    stored_values = (
        stored.subject_user_id,
        stored.index_text,
        stored.overview_text,
        stored.schema_version,
        stored.generator_version,
        stored.policy_version_id,
    )
    incoming_values = (
        record.subject_user_id,
        record.index_text,
        record.overview_text,
        record.schema_version,
        record.generator_version,
        record.policy_version_id,
    )
    links = tuple(
        ProfileClaimLinkRecord(item.claim_id, item.layer, item.position)
        for item in (
            await session.scalars(
                select(StoredProfileClaimLink)
                .where(StoredProfileClaimLink.profile_version_id == record.profile_version_id)
                .order_by(
                    StoredProfileClaimLink.layer,
                    StoredProfileClaimLink.position,
                    StoredProfileClaimLink.claim_id,
                )
            )
        ).all()
    )
    expected_links = tuple(sorted(record.claim_links, key=_link_key))
    if stored_values != incoming_values or links != expected_links:
        raise ValueError("profile version already exists")


async def _validate_active_profile(session: AsyncSession) -> None:
    states = (
        await session.execute(
            select(StoredProfileClaimLink.claim_id, StoredClaim.state)
            .join(StoredClaim, StoredClaim.claim_id == StoredProfileClaimLink.claim_id)
            .join(
                StoredProfileHead,
                StoredProfileHead.profile_version_id == StoredProfileClaimLink.profile_version_id,
            )
        )
    ).all()
    if any(state != "active" for _, state in states):
        raise ValueError("active profile cannot link a prompt-inactive claim")


def _link_key(link: ProfileClaimLinkRecord) -> tuple[str, int, str]:
    return (link.layer, link.position, link.claim_id)
