"""Platform-neutral values exchanged by context stages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from mika.conversation.contracts import ConversationEnvelope


@dataclass(frozen=True, slots=True)
class ContextMessage:
    """One ordered message selected from channel history."""

    role: str
    author_name: str
    content: str


@dataclass(frozen=True, slots=True)
class RetrievalScope:
    """Person and conversation visibility boundary applied before ranking."""

    subject_user_id: str
    visibility_kind: str
    guild_id: str | None
    channel_id: str | None


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    """One scoped memory with complete precomputed rendering tiers."""

    candidate_id: str
    subject_user_id: str
    visibility_kind: str
    guild_id: str | None
    channel_id: str | None
    kind: str
    index_text: str
    overview_text: str | None
    evidence_text: str | None
    evidence_class: str | None
    confidence: float
    observed_at: datetime
    score: float = 0.0
    score_components: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SelectedContext:
    """Bounded evidence prepared before participation and generation."""

    history: tuple[ContextMessage, ...] = ()
    memory: str = ""
    avoid_phrases: tuple[str, ...] = ()
    fact_count: int = 0
    match_count: int = 0
    feedback_count: int = 0
    relationship_retrieval: bool = False
    candidate_ids: tuple[str, ...] = ()
    selected_ids: tuple[str, ...] = ()
    rejected_ids: tuple[str, ...] = ()
    selected_tiers: Mapping[str, str] = field(default_factory=dict)
    rejection_reasons: Mapping[str, str] = field(default_factory=dict)
    estimated_token_cost: int = 0
    latency_ms: float = 0.0
    ranking_quality_signal: float = 0.0

    @property
    def trace_details(self) -> dict[str, object]:
        """Return counts only, never conversation content."""
        details: dict[str, object] = {
            "history_count": len(self.history),
            "avoid_phrase_count": len(self.avoid_phrases),
        }
        if self.memory or self.fact_count or self.match_count or self.feedback_count:
            details.update(
                fact_count=self.fact_count,
                match_count=self.match_count,
                feedback_count=self.feedback_count,
            )
        if self.relationship_retrieval:
            details.update(
                relationship_retrieval=True,
                candidate_ids=self.candidate_ids,
                selected_ids=self.selected_ids,
                rejected_ids=self.rejected_ids,
                selected_tiers=dict(self.selected_tiers),
                rejection_reasons=dict(self.rejection_reasons),
                estimated_token_cost=self.estimated_token_cost,
                latency_ms=self.latency_ms,
                ranking_quality_signal=self.ranking_quality_signal,
            )
        return details


@dataclass(frozen=True, slots=True)
class TurnObservation:
    """Visible result available for memory after Discord execution."""

    envelope: ConversationEnvelope
    reply: str
    intent: str
    confidence: float
    relationship_visible: bool = False
