"""Atomic lifecycle transitions for relationship-memory claims."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, update
from sqlalchemy.ext.asyncio import AsyncSession

from mika.persistence.conversations.relationship_integrity import (
    CURRENT_CLAIM_STATES,
    ScopedClaim,
    ScopedRecord,
    validate_activation,
    validate_predecessor,
    validate_predecessor_identity_scope,
    validate_replacement,
)
from mika.persistence.conversations.relationship_mapping import as_utc
from mika.persistence.conversations.relationship_models import StoredClaim


async def validate_new_predecessor(session: AsyncSession, replacement: ScopedClaim) -> None:
    """Validate and lock a new linked claim's current predecessor on every database."""
    predecessor_id = replacement.predecessor_claim_id
    if predecessor_id is None:
        return
    previous = await _require_claim(session, predecessor_id)
    try:
        validate_predecessor(previous, replacement)
    except ValueError:
        await session.rollback()
        raise
    await session.rollback()
    await _require_current_claim(session, predecessor_id)


async def activate_stored_claim(
    session: AsyncSession,
    stored: StoredClaim,
    *,
    confirmed_at: datetime,
) -> StoredClaim:
    """Activate a claim and atomically supersede its linked predecessor when needed."""
    try:
        validate_activation(stored.state)
    except ValueError:
        await session.rollback()
        raise
    predecessor_id = stored.predecessor_claim_id
    if predecessor_id is not None:
        stored = await _prepare_linked_activation(session, stored, predecessor_id, confirmed_at)
    stored.state = "active"
    stored.last_confirmed_at = as_utc(confirmed_at)
    return stored


async def transition_replacement(
    session: AsyncSession,
    previous: StoredClaim,
    replacement: ScopedClaim,
    evidence: ScopedRecord,
    *,
    superseded_at: datetime,
) -> None:
    """Validate a replacement, then atomically claim its predecessor transition."""
    try:
        validate_replacement(previous, replacement, evidence)
    except ValueError:
        await session.rollback()
        raise
    predecessor_id = previous.claim_id
    await session.rollback()
    await _supersede_current_claim(session, predecessor_id, superseded_at)


async def _prepare_linked_activation(
    session: AsyncSession,
    stored: StoredClaim,
    predecessor_id: str,
    confirmed_at: datetime,
) -> StoredClaim:
    previous = await _require_claim(session, predecessor_id)
    try:
        validate_predecessor_identity_scope(previous, stored)
    except ValueError:
        await session.rollback()
        raise
    if previous.state == "superseded" and stored.state == "active":
        return stored
    if previous.state not in CURRENT_CLAIM_STATES:
        await session.rollback()
        raise ValueError("predecessor is not current")
    claim_id = stored.claim_id
    await session.rollback()
    await _supersede_current_claim(session, predecessor_id, confirmed_at)
    return await _require_claim(session, claim_id)


async def _require_current_claim(session: AsyncSession, claim_id: str) -> None:
    statement = (
        update(StoredClaim)
        .where(
            StoredClaim.claim_id == claim_id,
            StoredClaim.state.in_(CURRENT_CLAIM_STATES),
        )
        .values(state=StoredClaim.state)
        .returning(StoredClaim.claim_id)
    )
    if await session.scalar(statement) is None:
        await session.rollback()
        raise ValueError("predecessor is not current")


async def _supersede_current_claim(
    session: AsyncSession, claim_id: str, superseded_at: datetime
) -> None:
    normalized_at = as_utc(superseded_at)
    statement = (
        update(StoredClaim)
        .where(
            StoredClaim.claim_id == claim_id,
            StoredClaim.state.in_(CURRENT_CLAIM_STATES),
        )
        .values(
            state="superseded",
            last_observed_at=case(
                (StoredClaim.last_observed_at < normalized_at, normalized_at),
                else_=StoredClaim.last_observed_at,
            ),
        )
        .returning(StoredClaim.claim_id)
    )
    if await session.scalar(statement) is None:
        await session.rollback()
        raise ValueError("predecessor is not current")


async def _require_claim(session: AsyncSession, claim_id: str) -> StoredClaim:
    stored = await session.get(StoredClaim, claim_id)
    if stored is None:
        await session.rollback()
        raise ValueError("claim does not exist")
    return stored
