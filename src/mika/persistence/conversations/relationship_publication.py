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
    StoredProfileHead,
    StoredProfileVersion,
)
from mika.persistence.conversations.relationship_records import (
    ClaimTransitionRecord,
    ProfileVersionRecord,
)

_ALLOWED_TRANSITIONS = {
    "candidate": frozenset({"active", "expired", "disputed", "superseded"}),
    "active": frozenset({"expired", "disputed", "superseded"}),
    "disputed": frozenset({"expired", "superseded"}),
}


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
    if await session.get(StoredProfileVersion, record.profile_version_id) is not None:
        raise ValueError("profile version already exists")
    if await session.get(StoredPolicyVersion, record.policy_version_id) is None:
        raise ValueError("policy version does not exist")
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
