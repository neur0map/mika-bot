"""Production-backed local runtime for relationship-memory evaluation."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from mika.conversation.context.retrieval import AffinityRetriever, MemoryRecall, merge_memory_text
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.relationships.activation import ActivationPolicy
from mika.conversation.relationships.consolidation import RelationshipConsolidator
from mika.conversation.relationships.contracts import RelationDecision
from mika.conversation.relationships.extraction import (
    EvidenceProposal,
    extract_deterministic_evidence,
)
from mika.conversation.relationships.relation import classify_relation
from mika.conversation.relationships.service import ObservationInput, RelationshipMemoryService
from mika.persistence.base import Base
from mika.persistence.conversations.relationship_memory import RelationshipMemoryRepository
from mika.persistence.conversations.relationship_records import (
    ClaimWrite,
    EvidenceWrite,
    RelationshipMemoryPolicyVersionRecord,
)

_TOKEN = re.compile(r"[a-z0-9']{3,}", re.IGNORECASE)


class _EmptySocialMemory:
    async def facts(self, user_id: str, *, limit: int = 12) -> list[tuple[str, str]]:
        del user_id, limit
        return []

    async def candidates(self, channel_id: str, author_id: str, *, limit: int = 80) -> tuple[()]:
        del channel_id, author_id, limit
        return ()

    async def feedback_summary(self, channel_id: str, *, limit: int = 100) -> dict[str, int]:
        del channel_id, limit
        return {}


class _DeterministicExtractor:
    async def extract(
        self, observation: ObservationInput, relation: RelationDecision
    ) -> tuple[EvidenceProposal, ...]:
        return extract_deterministic_evidence(
            observation.text,
            source_message_id=observation.message_id,
            source_timestamp=observation.created_at,
            relation=relation,
        )


class _Classifier:
    def classify(self, observation: ObservationInput) -> RelationDecision:
        return classify_relation(observation.text)


class _LocalSemanticScorer:
    def score(self, query: str, documents: Sequence[str]) -> tuple[float, ...]:
        query_terms = _terms(query)
        return tuple(_jaccard(query_terms, _terms(document)) for document in documents)


class _MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


class LocalBenchmarkBackend:
    """Run the actual service and retriever with no external provider dependency."""

    def __init__(
        self,
        engine: AsyncEngine,
        session: AsyncSession,
        repository: RelationshipMemoryRepository,
        service: RelationshipMemoryService,
        external_recall: Callable[[str], Awaitable[str]] | None,
        clock: _MutableClock,
        policy_version_id: str,
    ) -> None:
        self._engine = engine
        self._session = session
        self._repository = repository
        self._service = service
        self._external_recall = external_recall
        self._clock = clock
        self._policy_version_id = policy_version_id
        self._subjects: set[str] = set()
        self.lifecycle_snapshots: list[dict[str, int]] = []

    @classmethod
    async def create(
        cls,
        path: Path,
        mode: str,
        *,
        external_recall: Callable[[str], Awaitable[str]] | None = None,
    ) -> LocalBenchmarkBackend:
        """Create an empty benchmark store and production service graph."""
        engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session = AsyncSession(engine, expire_on_commit=False)
        repository = RelationshipMemoryRepository(session)
        await repository.write_policy_version(_policy(mode))
        semantic = None if mode == "lexical" else _LocalSemanticScorer()
        retriever = AffinityRetriever(
            _EmptySocialMemory(),
            match_limit=0,
            relationship_source=repository,
            semantic_scorer=semantic,
        )
        clock = _MutableClock()
        service = RelationshipMemoryService(
            repository=repository,
            extractor=_DeterministicExtractor(),
            activation_policy=ActivationPolicy(),
            classifier=_Classifier(),
            retriever=retriever,
            consolidator=RelationshipConsolidator(),
            clock=clock,
        )
        return cls(
            engine, session, repository, service, external_recall, clock, f"benchmark-policy-{mode}"
        )

    async def observe(self, observation: ObservationInput) -> None:
        self._clock.now = observation.created_at
        self._subjects.add(observation.subject_user_id)
        await self._service.observe_turn(observation)

    async def recall(self, observation: ObservationInput) -> MemoryRecall:
        self._clock.now = observation.created_at
        self._subjects.add(observation.subject_user_id)
        recall = await self._service.recall(_envelope(observation))
        if self._external_recall is None:
            return recall
        external = await self._external_recall(observation.text)
        return replace(
            recall,
            text=merge_memory_text(recall.text, external),
            estimated_token_cost=recall.estimated_token_cost + len(external.split()),
        )

    async def consolidate(self, observation: ObservationInput) -> None:
        self._clock.now = observation.created_at
        await self._service.consolidate_user(
            observation.subject_user_id,
            visibility_kind=observation.visibility_kind,
            guild_id=observation.guild_id,
            channel_id=observation.channel_id,
        )
        claims = await self._repository.claims_for_subject(observation.subject_user_id)
        self.lifecycle_snapshots.append(
            {
                state: sum(claim.state == state for claim in claims)
                for state in ("candidate", "active", "expired", "superseded", "disputed")
            }
        )

    async def seed_inference(self, observation: ObservationInput) -> None:
        self._clock.now = observation.created_at
        self._subjects.add(observation.subject_user_id)
        await self._repository.add_evidence(
            ClaimWrite(
                claim_id=f"benchmark-inference-{observation.message_id}",
                subject_user_id=observation.subject_user_id,
                visibility_kind=observation.visibility_kind,
                guild_id=observation.guild_id,
                channel_id=observation.channel_id,
                kind="care_pattern",
                key="inference:reply_tone",
                value="quiet",
                evidence_class="inference",
                confidence=0.5,
                state="candidate",
                predecessor_claim_id=None,
                observed_at=observation.created_at,
            ),
            EvidenceWrite(
                source_kind=observation.source_kind,
                source_id=observation.source_id,
                source_message_id=observation.message_id,
                source_timestamp=observation.created_at,
                visibility_kind=observation.visibility_kind,
                guild_id=observation.guild_id,
                channel_id=observation.channel_id,
                policy_version_id=self._policy_version_id,
            ),
        )

    def classify(self, observation: ObservationInput) -> RelationDecision:
        return classify_relation(observation.text)

    async def source_ids_for_candidates(self, candidate_ids: Sequence[str]) -> tuple[str, ...]:
        selected = set(candidate_ids)
        source_ids: list[str] = []
        for subject in sorted(self._subjects):
            claims = await self._repository.claims_for_subject(subject)
            for claim in claims:
                if claim.claim_id in selected:
                    source_ids.extend(claim.source_message_ids)
        return tuple(dict.fromkeys(source_ids))

    async def close(self) -> None:
        """Release the isolated store before its temporary directory is removed."""
        await self._session.close()
        await self._engine.dispose()


def _policy(mode: str) -> RelationshipMemoryPolicyVersionRecord:
    return RelationshipMemoryPolicyVersionRecord(
        policy_version_id=f"benchmark-policy-{mode}",
        relationship_learning_enabled=True,
        semantic_retrieval_enabled=mode != "lexical",
        provider_extraction_enabled=False,
        local_relation_model_enabled=False,
        visibility_rules={
            "guild": True,
            "direct_message": True,
            "channel": True,
            "global_explicit": True,
            "shadow_mode": False,
        },
        change_reason="held_out_benchmark",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


def _envelope(observation: ObservationInput) -> ConversationEnvelope:
    return ConversationEnvelope(
        observation.message_id,
        observation.channel_id or "benchmark",
        observation.guild_id or "",
        observation.subject_user_id,
        "held-out-user",
        observation.text,
        False,
        observation.created_at,
    )


def _terms(text: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN.finditer(text)}


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0
