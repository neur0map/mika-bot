"""Orchestrate evidence-backed relationship observation, recall, and consolidation."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, cast

from mika.conversation.context.retrieval import MemoryRecall
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.relationships.activation import ActivationPolicy
from mika.conversation.relationships.consolidation import (
    ConsolidationResult,
    RelationshipConsolidator,
)
from mika.conversation.relationships.contracts import (
    ClaimState,
    EvidenceClass,
    RelationDecision,
    RelationshipClaim,
)
from mika.conversation.relationships.extraction import EvidenceProposal
from mika.persistence.conversations.relationship_records import (
    ArchiveCursor,
    ArchiveSourceRecord,
    ClaimEvidenceRecord,
    ClaimRecord,
    ClaimWrite,
    EvidenceWrite,
    ProfileVersionRecord,
    RecallEventWrite,
    RelationshipMemoryPolicyVersionRecord,
)


@dataclass(frozen=True, slots=True)
class ObservationInput:
    """One source message eligible for relationship evidence extraction."""

    source_kind: str
    source_id: str
    message_id: str
    subject_user_id: str
    text: str
    created_at: datetime
    visibility_kind: str
    guild_id: str | None
    channel_id: str | None

    @classmethod
    def from_envelope(cls, envelope: ConversationEnvelope) -> ObservationInput:
        """Build a live observation after the caller confirms visible execution."""
        visibility = "guild" if envelope.guild_id else "direct_message"
        return cls(
            "discord",
            envelope.message_id,
            envelope.message_id,
            envelope.author_id,
            envelope.text,
            envelope.created_at,
            visibility,
            envelope.guild_id or None,
            envelope.channel_id,
        )

    @classmethod
    def from_archive(cls, source: ArchiveSourceRecord) -> ObservationInput:
        """Build an observation from one validated archive source row."""
        return cls(
            source.source_kind,
            source.source_id,
            source.discord_message_id,
            source.author_id,
            source.text,
            source.archive_created_at,
            source.visibility_kind,
            source.guild_id,
            source.channel_id,
        )


@dataclass(frozen=True, slots=True)
class ObservationResult:
    """Content-free outcome for one relationship observation."""

    outcome: str
    policy_version_id: str | None
    candidate_count: int = 0
    activated_count: int = 0


@dataclass(frozen=True, slots=True)
class PendingObservationResult:
    """Bounded archive processing outcome suitable for scheduler telemetry."""

    processed: int
    remaining_hint: bool
    policy_version_id: str | None
    failed_message_id: str | None = None
    retry_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ConsolidationRun:
    """Content-free publication result for one subject consolidation."""

    profile_changed: bool
    policy_version_id: str | None
    profile_version_id: str | None = None
    candidate_count: int = 0
    rejected: bool = False


class RelationshipRepository(Protocol):
    """Persistence operations required by relationship orchestration."""

    async def active_policy_version(self) -> RelationshipMemoryPolicyVersionRecord | None: ...
    async def add_evidence(self, claim: ClaimWrite, evidence: EvidenceWrite) -> ClaimRecord: ...
    async def activate_claim(self, claim_id: str, *, confirmed_at: datetime) -> ClaimRecord: ...
    async def claims_for_subject(
        self, subject_user_id: str, *, limit: int = 1000
    ) -> Sequence[ClaimRecord]: ...
    async def evidence_for_claims(
        self, claim_ids: Sequence[str]
    ) -> Sequence[ClaimEvidenceRecord]: ...
    async def active_profile(self, subject_user_id: str) -> ProfileVersionRecord | None: ...
    async def write_profile_version(self, record: ProfileVersionRecord) -> None: ...
    async def record_recall(self, event: RecallEventWrite) -> None: ...
    async def cursor(self, source_name: str) -> ArchiveCursor | None: ...
    async def advance_cursor(self, cursor: ArchiveCursor) -> None: ...


class EvidenceExtractor(Protocol):
    """Potentially provider-backed extraction boundary."""

    async def extract(
        self, observation: ObservationInput, relation: RelationDecision
    ) -> Sequence[EvidenceProposal]: ...


class RelationClassifier(Protocol):
    """Relation classification boundary."""

    def classify(self, observation: ObservationInput) -> RelationDecision: ...


class RelationshipRetriever(Protocol):
    """Scoped relationship-retrieval boundary."""

    async def retrieve(self, envelope: ConversationEnvelope) -> MemoryRecall: ...


class PendingObservationSource(Protocol):
    """Read-only source used by the bounded background job."""

    def iter_after(
        self, cursor: ArchiveCursor | None, limit: int
    ) -> Sequence[ArchiveSourceRecord]: ...


class RelationshipMemoryService:
    """Coordinate relationship memory without Discord or provider coupling."""

    def __init__(
        self,
        *,
        repository: RelationshipRepository,
        extractor: EvidenceExtractor,
        activation_policy: ActivationPolicy,
        classifier: RelationClassifier,
        retriever: RelationshipRetriever,
        consolidator: RelationshipConsolidator,
        pending_source: PendingObservationSource | None = None,
        pending_source_name: str = "shared_archive",
        batch_size: int = 50,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._repository = repository
        self._extractor = extractor
        self._activation_policy = activation_policy
        self._classifier = classifier
        self._retriever = retriever
        self._consolidator = consolidator
        self.pending_source = pending_source
        self._pending_source_name = pending_source_name
        self._batch_size = batch_size
        self._clock = clock or (lambda: datetime.now(UTC))

    async def observe_turn(self, observation: ObservationInput) -> ObservationResult:
        """Extract and persist one completed visible turn under its effective policy."""
        policy = await self._repository.active_policy_version()
        if policy is None or not policy.relationship_learning_enabled:
            policy_id = None if policy is None else policy.policy_version_id
            return ObservationResult("disabled", policy_id)
        relation = self._classify(observation)
        proposals = tuple(await self._extractor.extract(observation, relation))
        activated = 0
        for proposal in proposals:
            activated += await self._persist_proposal(observation, proposal, policy)
        return ObservationResult("observed", policy.policy_version_id, len(proposals), activated)

    async def recall(self, envelope: ConversationEnvelope) -> MemoryRecall:
        """Retrieve scoped prompt memory and persist an idempotent content-free trace."""
        policy = await self._repository.active_policy_version()
        recalled = await self._retriever.retrieve(envelope)
        if policy is None or not policy.relationship_learning_enabled:
            return recalled
        relation = self._classify(ObservationInput.from_envelope(envelope))
        await self._repository.record_recall(
            RecallEventWrite(
                recall_event_id=_stable_id("recall", policy.policy_version_id, envelope.message_id),
                subject_user_id=envelope.author_id,
                visibility_kind="guild" if envelope.guild_id else "direct_message",
                guild_id=envelope.guild_id or None,
                channel_id=envelope.channel_id,
                query_hash=f"sha256:{hashlib.sha256(envelope.text.encode()).hexdigest()}",
                relation_label=relation.relation,
                candidate_ids=recalled.candidate_ids,
                selected_claim_ids=recalled.selected_ids,
                selected_tiers=recalled.selected_tiers,
                rejection_reasons=recalled.rejection_reasons,
                estimated_token_cost=recalled.estimated_token_cost,
                latency_ms=recalled.latency_ms,
                retrieval_version="relationship-service-v1",
                policy_version_id=policy.policy_version_id,
                created_at=self._clock(),
            )
        )
        return recalled

    async def consolidate_user(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> ConsolidationRun:
        """Promote full claim history and publish a profile only when content changes."""
        policy = await self._repository.active_policy_version()
        if policy is None or not policy.relationship_learning_enabled:
            return ConsolidationRun(False, None if policy is None else policy.policy_version_id)
        records = tuple(await self._repository.claims_for_subject(subject_user_id))
        evidence = tuple(
            await self._repository.evidence_for_claims([item.claim_id for item in records])
        )
        result = self._consolidator.consolidate(
            tuple(_relationship_claim(item) for item in records),
            evidence_by_claim_id=_evidence_by_claim(records, evidence),
            now=self._clock(),
        )
        await self._publish_activations(records, result)
        return await self._publish_profile(subject_user_id, policy.policy_version_id, result)

    async def run_pending_observations(
        self, *, limit: int | None = None
    ) -> PendingObservationResult:
        """Process at most one bounded archive batch and stop at the first failure."""
        bound = self._batch_size if limit is None else min(limit, self._batch_size)
        if bound < 1:
            raise ValueError("pending observation limit must be positive")
        policy = await self._repository.active_policy_version()
        policy_id = None if policy is None else policy.policy_version_id
        if policy is None or not policy.relationship_learning_enabled:
            return PendingObservationResult(0, False, policy_id)
        policy_id = policy.policy_version_id
        if self.pending_source is None:
            raise RuntimeError("pending observation source is not configured")
        cursor = await self._repository.cursor(self._pending_source_name)
        sources = tuple(self.pending_source.iter_after(cursor, bound + 1))
        processed = 0
        for source in sources[:bound]:
            try:
                await self.observe_turn(ObservationInput.from_archive(source))
            except Exception as error:
                return PendingObservationResult(
                    processed, True, policy_id, source.discord_message_id, type(error).__name__
                )
            await self._repository.advance_cursor(
                ArchiveCursor(
                    self._pending_source_name,
                    source.archive_created_at,
                    source.discord_message_id,
                    policy_id,
                    self._clock(),
                )
            )
            processed += 1
        return PendingObservationResult(processed, len(sources) > bound, policy_id)

    def _classify(self, observation: ObservationInput) -> RelationDecision:
        try:
            return self._classifier.classify(observation)
        except Exception:
            return RelationDecision("follow_up", 0.5, "classifier_failure", ("fallback",))

    async def _persist_proposal(
        self,
        observation: ObservationInput,
        proposal: EvidenceProposal,
        policy: RelationshipMemoryPolicyVersionRecord,
    ) -> int:
        history = tuple(await self._repository.claims_for_subject(observation.subject_user_id))
        claim_id = _claim_id(observation, proposal)
        existing = next((item for item in history if item.claim_id == claim_id), None)
        predecessor = _correction_predecessor(history, proposal, observation)
        if existing is not None:
            predecessor_id, claim_key = existing.predecessor_claim_id, existing.key
        elif predecessor is not None:
            predecessor_id, claim_key = predecessor.claim_id, predecessor.key
        else:
            predecessor_id, claim_key = None, proposal.key
        claim = _claim_write(claim_id, claim_key, predecessor_id, observation, proposal)
        evidence = _evidence_write(observation, policy.policy_version_id)
        stored = await self._repository.add_evidence(claim, evidence)
        all_evidence = tuple(await self._repository.evidence_for_claims([claim_id]))
        decision = self._activation_policy.evaluate(
            _relationship_claim(stored),
            tuple(_proposal_from_record(item, stored) for item in all_evidence),
        )
        if decision.state != "active":
            return 0
        await self._repository.activate_claim(claim_id, confirmed_at=observation.created_at)
        return int(stored.state != "active")

    async def _publish_activations(
        self, records: Sequence[ClaimRecord], result: ConsolidationResult
    ) -> None:
        prior = {item.claim_id: item.state for item in records}
        for claim in result.claims:
            if claim.state == "active" and prior.get(claim.claim_id) == "candidate":
                await self._repository.activate_claim(claim.claim_id, confirmed_at=self._clock())

    async def _publish_profile(
        self, subject_user_id: str, policy_version_id: str, result: ConsolidationResult
    ) -> ConsolidationRun:
        profile = result.profile
        if profile is None:
            return ConsolidationRun(False, policy_version_id, candidate_count=len(result.claims))
        active = await self._repository.active_profile(subject_user_id)
        if active is not None and (
            active.index_text,
            active.overview_text,
        ) == (profile.index_text, profile.overview_text):
            return ConsolidationRun(
                False,
                policy_version_id,
                active.profile_version_id,
                len(result.claims),
                result.rejected,
            )
        version_id = _stable_id(
            "profile", subject_user_id, policy_version_id, profile.index_text, profile.overview_text
        )
        await self._repository.write_profile_version(
            ProfileVersionRecord(
                version_id,
                subject_user_id,
                profile.index_text,
                profile.overview_text,
                "relationship-profile-v1",
                "deterministic-v1",
                policy_version_id,
                self._clock(),
            )
        )
        return ConsolidationRun(
            True, policy_version_id, version_id, len(result.claims), result.rejected
        )


def _claim_write(
    claim_id: str,
    claim_key: str,
    predecessor_id: str | None,
    observation: ObservationInput,
    proposal: EvidenceProposal,
) -> ClaimWrite:
    return ClaimWrite(
        claim_id,
        observation.subject_user_id,
        observation.visibility_kind,
        observation.guild_id,
        observation.channel_id,
        proposal.kind,
        claim_key,
        proposal.value,
        proposal.evidence_class,
        proposal.confidence,
        "candidate",
        predecessor_id,
        observation.created_at,
    )


def _evidence_write(observation: ObservationInput, policy_version_id: str) -> EvidenceWrite:
    return EvidenceWrite(
        observation.source_kind,
        observation.source_id,
        observation.message_id,
        observation.created_at,
        observation.visibility_kind,
        observation.guild_id,
        observation.channel_id,
        policy_version_id,
    )


def _relationship_claim(record: ClaimRecord) -> RelationshipClaim:
    return RelationshipClaim(
        record.claim_id,
        record.subject_user_id,
        record.guild_id,
        record.channel_id,
        record.kind,
        record.key,
        record.value,
        cast(EvidenceClass, record.evidence_class),
        record.confidence,
        record.source_message_ids,
        record.observation_count,
        record.first_observed_at,
        record.last_observed_at,
        record.last_confirmed_at,
        cast(ClaimState, record.state),
        record.predecessor_claim_id,
    )


def _proposal_from_record(record: ClaimEvidenceRecord, claim: ClaimRecord) -> EvidenceProposal:
    return EvidenceProposal(
        claim.kind,
        claim.key,
        claim.value,
        cast(EvidenceClass, claim.evidence_class),
        claim.confidence,
        record.source_message_id,
        record.source_timestamp,
        "stored_evidence",
    )


def _evidence_by_claim(
    claims: Sequence[ClaimRecord], evidence: Sequence[ClaimEvidenceRecord]
) -> Mapping[str, Sequence[EvidenceProposal]]:
    by_id = {item.claim_id: item for item in claims}
    grouped: dict[str, list[EvidenceProposal]] = defaultdict(list)
    for item in evidence:
        claim = by_id.get(item.claim_id)
        if claim is not None:
            grouped[item.claim_id].append(_proposal_from_record(item, claim))
    return grouped


def _correction_predecessor(
    claims: Sequence[ClaimRecord],
    proposal: EvidenceProposal,
    observation: ObservationInput,
) -> ClaimRecord | None:
    if proposal.evidence_class != "correction":
        return None
    normalized_key = " ".join(proposal.key.casefold().split())
    candidates = [
        item
        for item in claims
        if item.state == "active"
        and item.subject_user_id == observation.subject_user_id
        and item.kind == proposal.kind
        and " ".join(item.key.casefold().split()) == normalized_key
        and item.value != proposal.value
        and item.visibility_kind == observation.visibility_kind
        and item.guild_id == observation.guild_id
        and item.channel_id == observation.channel_id
    ]
    return max(candidates, key=lambda item: item.last_observed_at) if candidates else None


def _claim_id(observation: ObservationInput, proposal: EvidenceProposal) -> str:
    return _stable_id(
        "claim",
        observation.subject_user_id,
        observation.visibility_kind,
        observation.guild_id or "",
        observation.channel_id or "",
        proposal.kind,
        proposal.key,
        proposal.value,
        proposal.evidence_class,
    )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256(chr(0).join(parts).encode()).hexdigest()
    return f"{prefix}-{digest[:24]}"
