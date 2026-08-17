"""Immutable values for evidence-backed relationship memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

RelationKind = Literal[
    "follow_up",
    "correction",
    "new_topic",
    "topic_end",
    "social_check_in",
    "memory_probe",
]
EvidenceClass = Literal["explicit", "correction", "repeated_behavior", "reaction", "inference"]
ClaimState = Literal["candidate", "active", "disputed", "superseded", "expired"]
MemoryLayer = Literal["index", "overview", "evidence"]


@dataclass(frozen=True, slots=True)
class RelationDecision:
    """Classify how an incoming message relates to the current conversation."""

    relation: RelationKind
    confidence: float
    reason: str
    signals: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RelationshipClaim:
    """One evidence-backed fact used to build a person's relationship profile."""

    claim_id: str
    subject_user_id: str
    guild_id: str | None
    channel_id: str | None
    kind: str
    key: str
    value: str
    evidence_class: EvidenceClass
    confidence: float
    source_message_ids: tuple[str, ...]
    observation_count: int
    first_observed_at: datetime
    last_observed_at: datetime
    last_confirmed_at: datetime | None
    state: ClaimState = "candidate"
    predecessor_claim_id: str | None = None
