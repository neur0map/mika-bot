"""Bounded legacy affinity and scoped relationship-memory retrieval."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from time import perf_counter
from typing import Protocol

from mika.conversation.context.contracts import MemoryCandidate
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.relationships.candidates import (
    as_aware,
    claim_candidates,
    message_candidate,
    scope_for_envelope,
)
from mika.conversation.relationships.contracts import RelationDecision
from mika.conversation.relationships.relation import classify_relation
from mika.conversation.relationships.rendering import TieredMemoryRenderer
from mika.conversation.relationships.scoring import (
    AttributedRecallFeedback,
    HybridMemoryScorer,
    SemanticScorer,
)
from mika.core.logging import get_logger
from mika.persistence.conversations.relationship_records import ClaimRecord, ProfileVersionRecord

_TOKEN = re.compile(r"[a-z0-9']{3,}", re.I)
_CANDIDATE_LIMIT = 80
logger = get_logger(__name__)


class CandidateMessage(Protocol):
    channel_id: str
    author_id: str
    author_name: str
    content: str


class SocialMemorySource(Protocol):
    async def facts(self, user_id: str, *, limit: int = 12) -> list[tuple[str, str]]: ...

    async def candidates(
        self, channel_id: str, author_id: str, *, limit: int = _CANDIDATE_LIMIT
    ) -> Sequence[CandidateMessage]: ...

    async def feedback_summary(self, channel_id: str, *, limit: int = 100) -> dict[str, int]: ...


class RelationshipMemorySource(Protocol):
    """Scoped persistence capabilities used by relationship retrieval."""

    async def claims_for_user(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
        limit: int = 100,
    ) -> Sequence[ClaimRecord]: ...

    async def active_profile_for_scope(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> ProfileVersionRecord | None: ...


class ContextRetriever(Protocol):
    """One fail-open context source used by merged retrieval."""

    async def retrieve(self, envelope: ConversationEnvelope) -> MemoryRecall: ...


@dataclass(frozen=True, slots=True)
class MemoryRecall:
    """Compact prompt context plus privacy-safe counts for tracing."""

    text: str = ""
    fact_count: int = 0
    match_count: int = 0
    feedback_count: int = 0
    relationship_retrieval: bool = False
    candidate_ids: tuple[str, ...] = ()
    selected_ids: tuple[str, ...] = ()
    rejected_ids: tuple[str, ...] = ()
    selected_tiers: dict[str, str] = field(default_factory=dict)
    rejection_reasons: dict[str, str] = field(default_factory=dict)
    estimated_token_cost: int = 0
    latency_ms: float = 0.0
    ranking_quality_signal: float = 0.0

    @property
    def trace_details(self) -> dict[str, object]:
        details: dict[str, object] = {
            "fact_count": self.fact_count,
            "match_count": self.match_count,
            "feedback_count": self.feedback_count,
        }
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


class MergedRetriever:
    """Merge independent recall sources while removing repeated prompt sections."""

    def __init__(self, *retrievers: ContextRetriever) -> None:
        self._retrievers = retrievers

    async def retrieve(self, envelope: ConversationEnvelope) -> MemoryRecall:
        """Return all available recalls even when one source fails."""
        recalls: list[MemoryRecall] = []
        for retriever in self._retrievers:
            try:
                recalls.append(await retriever.retrieve(envelope))
            except Exception as error:
                logger.warning("context recall source failed: %s", type(error).__name__)
                continue
        return _merge_recalls(recalls)


class AffinityRetriever:
    """Rank bounded candidates without an external vector service."""

    def __init__(
        self,
        source: SocialMemorySource,
        *,
        match_limit: int = 4,
        relationship_source: RelationshipMemorySource | None = None,
        relationship_candidates: Sequence[MemoryCandidate] = (),
        semantic_scorer: SemanticScorer | None = None,
        attributed_feedback: Sequence[AttributedRecallFeedback] = (),
        relation_decision: RelationDecision | None = None,
        token_budget: int = 700,
        per_entry_token_cap: int = 180,
        minimum_score: float = 0.8,
    ) -> None:
        self._source = source
        self._match_limit = max(0, match_limit)
        self._relationship_source = relationship_source
        self._relationship_candidates = tuple(relationship_candidates)
        self._semantic_scorer = semantic_scorer
        self._attributed_feedback = tuple(attributed_feedback)
        self._relation_decision = relation_decision
        self._scorer = HybridMemoryScorer(minimum_score=minimum_score)
        self._renderer = TieredMemoryRenderer(
            token_budget=token_budget,
            per_entry_token_cap=per_entry_token_cap,
        )

    async def retrieve(self, envelope: ConversationEnvelope) -> MemoryRecall:
        """Return legacy recall or the explicitly enabled scoped replacement."""
        if self._relationship_source is not None:
            started = perf_counter()
            try:
                return await self._retrieve_relationship(envelope)
            except Exception:
                return MemoryRecall(
                    relationship_retrieval=True,
                    rejection_reasons={"relationship_retrieval": "source_failure"},
                    latency_ms=(perf_counter() - started) * 1000,
                )
        return await self._retrieve_legacy(envelope)

    async def _retrieve_legacy(self, envelope: ConversationEnvelope) -> MemoryRecall:
        facts = await self._source.facts(envelope.author_id)
        candidates = await self._source.candidates(envelope.channel_id, envelope.author_id)
        feedback = await self._source.feedback_summary(envelope.channel_id)
        query_terms = _terms(envelope.text)
        scored: list[tuple[int, CandidateMessage]] = []
        for candidate in candidates:
            overlap = len(query_terms & _terms(candidate.content))
            affinity = 3 if candidate.author_id == envelope.author_id else 0
            channel = 1 if candidate.channel_id == envelope.channel_id else 0
            if overlap == 0 and affinity == 0:
                continue
            score = overlap * 2 + affinity + channel
            scored.append((score, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        matches = [candidate for _, candidate in scored[: self._match_limit]]
        sections: list[str] = []
        if facts:
            sections.append(
                "Known explicit user facts:\n"
                + "\n".join(f"- {key.replace('_', ' ')}: {value}" for key, value in facts)
            )
        if matches:
            sections.append(
                "Potentially relevant past messages:\n"
                + "\n".join(f"- {item.author_name}: {item.content[:240]}" for item in matches)
            )
        if feedback:
            summary = ", ".join(f"{signal}={count}" for signal, count in sorted(feedback.items()))
            sections.append(f"Recent reactions to Mika in this channel (aggregate only): {summary}")
        return MemoryRecall(
            "\n\n".join(sections),
            len(facts),
            len(matches),
            sum(feedback.values()),
        )

    async def _retrieve_relationship(self, envelope: ConversationEnvelope) -> MemoryRecall:
        started = perf_counter()
        scope = scope_for_envelope(envelope)
        relationship_source = self._relationship_source
        if relationship_source is None:
            return MemoryRecall()
        claims = await relationship_source.claims_for_user(
            envelope.author_id,
            visibility_kind=scope.visibility_kind,
            guild_id=scope.guild_id,
            channel_id=scope.channel_id,
        )
        messages = await self._source.candidates(envelope.channel_id, envelope.author_id)
        candidates = [*claim_candidates(claims), *self._relationship_candidates]
        candidates.extend(message_candidate(item, envelope, scope) for item in messages)
        ranking = self._scorer.rank(
            envelope.text,
            candidates,
            scope,
            now=as_aware(envelope.created_at),
            semantic_scorer=self._semantic_scorer,
            feedback=self._attributed_feedback,
        )
        ranked, limit_rejections = _limit_messages(ranking.ranked, self._match_limit)
        relation = self._relation_decision or classify_relation(envelope.text)
        rendered = self._renderer.render(ranked, relation)
        reasons = {
            **ranking.rejection_reasons,
            **limit_rejections,
            **rendered.rejection_reasons,
        }
        selected = set(rendered.selected_ids)
        candidate_ids = tuple(item.candidate_id for item in candidates)
        rejected_ids = tuple(
            candidate_id
            for candidate_id in candidate_ids
            if candidate_id in reasons and candidate_id not in selected
        )
        selected_candidates = {
            item.candidate_id: item for item in ranked if item.candidate_id in selected
        }
        return MemoryRecall(
            text=rendered.text,
            fact_count=sum(item.kind == "claim" for item in selected_candidates.values()),
            match_count=sum(item.kind == "message" for item in selected_candidates.values()),
            feedback_count=len(self._attributed_feedback),
            relationship_retrieval=True,
            candidate_ids=candidate_ids,
            selected_ids=rendered.selected_ids,
            rejected_ids=rejected_ids,
            selected_tiers=dict(rendered.selected_tiers),
            rejection_reasons=reasons,
            estimated_token_cost=rendered.estimated_token_cost,
            latency_ms=(perf_counter() - started) * 1000,
            ranking_quality_signal=ranking.ranking_quality_signal,
        )


def _terms(text: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN.finditer(text)}


def merge_memory_text(*values: str) -> str:
    """Join nonempty memory sections once using normalized exact deduplication."""
    sections: list[str] = []
    seen: set[str] = set()
    for value in values:
        for section in value.split("\n\n"):
            rendered = section.strip()
            key = " ".join(rendered.casefold().split())
            if rendered and key not in seen:
                sections.append(rendered)
                seen.add(key)
    return "\n\n".join(sections)


def _merge_recalls(recalls: Sequence[MemoryRecall]) -> MemoryRecall:
    return MemoryRecall(
        text=merge_memory_text(*(item.text for item in recalls)),
        fact_count=sum(item.fact_count for item in recalls),
        match_count=sum(item.match_count for item in recalls),
        feedback_count=sum(item.feedback_count for item in recalls),
        relationship_retrieval=any(item.relationship_retrieval for item in recalls),
        candidate_ids=_unique(item for recall in recalls for item in recall.candidate_ids),
        selected_ids=_unique(item for recall in recalls for item in recall.selected_ids),
        rejected_ids=_unique(item for recall in recalls for item in recall.rejected_ids),
        selected_tiers={
            key: value for item in recalls for key, value in item.selected_tiers.items()
        },
        rejection_reasons={
            key: value for item in recalls for key, value in item.rejection_reasons.items()
        },
        estimated_token_cost=sum(item.estimated_token_cost for item in recalls),
        latency_ms=sum(item.latency_ms for item in recalls),
        ranking_quality_signal=max((item.ranking_quality_signal for item in recalls), default=0.0),
    )


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _limit_messages(
    candidates: Sequence[MemoryCandidate], limit: int
) -> tuple[list[MemoryCandidate], dict[str, str]]:
    selected: list[MemoryCandidate] = []
    rejected: dict[str, str] = {}
    message_count = 0
    for candidate in candidates:
        if candidate.kind != "message":
            selected.append(candidate)
        elif message_count < limit:
            selected.append(candidate)
            message_count += 1
        else:
            rejected[candidate.candidate_id] = "match_limit"
    return selected, rejected
