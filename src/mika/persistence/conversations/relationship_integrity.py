"""Integrity checks for scoped relationship-memory persistence records."""

from __future__ import annotations

from typing import Protocol

_MAX_SNOWFLAKE = "18446744073709551615"
CURRENT_CLAIM_STATES = ("active", "candidate", "disputed")


class ScopedRecord(Protocol):
    """Structural scope fields shared by claims, evidence, and stored rows."""

    @property
    def visibility_kind(self) -> str:
        """Return the scope category."""
        ...

    @property
    def guild_id(self) -> str | None:
        """Return the scoped guild when applicable."""
        ...

    @property
    def channel_id(self) -> str | None:
        """Return the scoped channel when applicable."""
        ...


class ScopedClaim(ScopedRecord, Protocol):
    """Claim identity and lifecycle fields needed for correction checks."""

    @property
    def claim_id(self) -> str: ...

    @property
    def subject_user_id(self) -> str: ...

    @property
    def key(self) -> str: ...

    @property
    def state(self) -> str: ...

    @property
    def predecessor_claim_id(self) -> str | None: ...


def validate_claim_evidence_scope(claim: ScopedRecord, evidence: ScopedRecord) -> None:
    """Reject a claim whose visibility exceeds its supporting evidence."""
    if not _scope_contains(evidence, claim):
        raise ValueError("claim scope cannot be wider than evidence scope")


def validate_activation(state: str) -> None:
    """Reject activation from a terminal lifecycle state."""
    if state not in CURRENT_CLAIM_STATES:
        raise ValueError(f"cannot activate claim in {state} state")


def validate_predecessor(previous: ScopedClaim, replacement: ScopedClaim) -> None:
    """Reject a replacement that is unrelated, wider, or no longer current."""
    validate_predecessor_identity_scope(previous, replacement)
    if previous.state not in CURRENT_CLAIM_STATES:
        raise ValueError("predecessor is not current")


def validate_predecessor_identity_scope(previous: ScopedClaim, replacement: ScopedClaim) -> None:
    """Require a replacement to preserve its predecessor's identity and visibility."""
    if replacement.predecessor_claim_id != previous.claim_id:
        raise ValueError("replacement predecessor does not match superseded claim")
    if (replacement.subject_user_id, replacement.key) != (
        previous.subject_user_id,
        previous.key,
    ):
        raise ValueError("replacement subject and key must match")
    if not _scope_contains(previous, replacement):
        raise ValueError("replacement cannot widen predecessor scope")


def validate_replacement(
    previous: ScopedClaim,
    replacement: ScopedClaim,
    evidence: ScopedRecord,
) -> None:
    """Validate a correction before changing either claim in its transaction."""
    validate_predecessor(previous, replacement)
    validate_claim_evidence_scope(replacement, evidence)


def normalize_discord_message_id(value: str) -> str:
    """Return the canonical decimal form of a positive Discord snowflake."""
    if not value or not value.isascii() or not value.isdecimal():
        raise ValueError("Discord message ID must be a positive integer")
    normalized = value.lstrip("0")
    if (
        not normalized
        or len(normalized) > len(_MAX_SNOWFLAKE)
        or (len(normalized) == len(_MAX_SNOWFLAKE) and normalized > _MAX_SNOWFLAKE)
    ):
        raise ValueError("Discord message ID must be a positive integer")
    return normalized


def _scope_contains(outer: ScopedRecord, inner: ScopedRecord) -> bool:
    if outer.visibility_kind == "global_explicit":
        return True
    if outer.visibility_kind == "guild":
        return (
            outer.guild_id is not None
            and inner.guild_id == outer.guild_id
            and inner.visibility_kind in {"guild", "channel"}
        )
    if outer.visibility_kind == "channel":
        return (
            outer.guild_id is not None
            and outer.channel_id is not None
            and inner.visibility_kind == "channel"
            and inner.guild_id == outer.guild_id
            and inner.channel_id == outer.channel_id
        )
    if outer.visibility_kind == "direct_message":
        return (
            outer.guild_id is None
            and outer.channel_id is not None
            and inner.visibility_kind == "direct_message"
            and inner.guild_id is None
            and inner.channel_id == outer.channel_id
        )
    return False
