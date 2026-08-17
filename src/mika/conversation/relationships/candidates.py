"""Build scoped rendering candidates from persistence and message records."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol

from mika.conversation.context.contracts import MemoryCandidate, RetrievalScope
from mika.conversation.contracts import ConversationEnvelope
from mika.persistence.conversations.relationship_records import ClaimRecord, ProfileVersionRecord


class CandidateMessageData(Protocol):
    """Message fields required to build a scoped retrieval candidate."""

    channel_id: str
    author_id: str
    content: str


def scope_for_envelope(envelope: ConversationEnvelope) -> RetrievalScope:
    """Derive the strict current visibility scope from an incoming turn."""
    visibility = "guild" if envelope.guild_id else "direct_message"
    return RetrievalScope(
        envelope.author_id,
        visibility,
        envelope.guild_id or None,
        envelope.channel_id,
    )


def claim_candidates(claims: Sequence[ClaimRecord]) -> list[MemoryCandidate]:
    """Build complete index, overview, and evidence tiers for stored claims."""
    candidates: list[MemoryCandidate] = []
    for claim in claims:
        key = claim.key.replace("_", " ")
        index_text = f"{key}: {claim.value}"
        overview_text = f"{claim.kind}: {key}: {claim.value}"
        source_ids = ", ".join(claim.source_message_ids)
        evidence_text = f"{overview_text}. Sources: {source_ids}" if source_ids else overview_text
        candidates.append(
            MemoryCandidate(
                candidate_id=claim.claim_id,
                subject_user_id=claim.subject_user_id,
                visibility_kind=claim.visibility_kind,
                guild_id=claim.guild_id,
                channel_id=claim.channel_id,
                kind="claim",
                index_text=index_text,
                overview_text=overview_text,
                evidence_text=evidence_text,
                evidence_class=claim.evidence_class,
                confidence=claim.confidence,
                observed_at=as_aware(claim.last_confirmed_at or claim.last_observed_at),
            )
        )
    return candidates


def profile_candidate(profile: ProfileVersionRecord, scope: RetrievalScope) -> MemoryCandidate:
    """Build a DM-only candidate from an installation-wide profile overview."""
    return MemoryCandidate(
        candidate_id=f"profile:{profile.profile_version_id}",
        subject_user_id=profile.subject_user_id,
        visibility_kind="direct_message",
        guild_id=None,
        channel_id=scope.channel_id,
        kind="profile",
        index_text=profile.index_text,
        overview_text=profile.overview_text,
        evidence_text=None,
        evidence_class=None,
        confidence=1.0,
        observed_at=as_aware(profile.created_at),
    )


def message_candidate(
    message: CandidateMessageData,
    envelope: ConversationEnvelope,
    scope: RetrievalScope,
) -> MemoryCandidate:
    """Build a bounded index candidate from one locally stored message."""
    raw_id = getattr(message, "id", None)
    if isinstance(raw_id, str | int):
        identifier = str(raw_id)
    else:
        identifier = hashlib.sha256(
            f"{message.channel_id}\0{message.author_id}\0{message.content}".encode()
        ).hexdigest()[:16]
    raw_created_at = getattr(message, "created_at", envelope.created_at)
    created_at = raw_created_at if isinstance(raw_created_at, datetime) else envelope.created_at
    return MemoryCandidate(
        candidate_id=f"message:{identifier}",
        subject_user_id=message.author_id,
        visibility_kind="direct_message"
        if scope.visibility_kind == "direct_message"
        else "channel",
        guild_id=scope.guild_id,
        channel_id=message.channel_id,
        kind="message",
        index_text=" ".join(message.content.split()[:40]),
        overview_text=None,
        evidence_text=None,
        evidence_class=None,
        confidence=0.5,
        observed_at=as_aware(created_at),
    )


def as_aware(value: datetime) -> datetime:
    """Normalize repository timestamps to aware UTC values for recency scoring."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
