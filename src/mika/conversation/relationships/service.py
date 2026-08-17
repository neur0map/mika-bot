"""Orchestrate evidence-backed relationship observation, recall, and consolidation."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from time import perf_counter
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
from mika.conversation.relationships.profile import ProfileEntry, RelationshipProfile
from mika.conversation.relationships.telemetry import RelationshipTelemetry
from mika.persistence.conversations.relationship_records import (
    ArchiveCursor,
    ArchiveSourceRecord,
    ClaimEvidenceRecord,
    ClaimRecord,
    ClaimTransitionRecord,
    ClaimWrite,
    EvidenceWrite,
    ProfileClaimLinkRecord,
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
    async def claims_for_subject(self, subject_user_id: str) -> Sequence[ClaimRecord]: ...
    async def evidence_for_claims(
        self, claim_ids: Sequence[str]
    ) -> Sequence[ClaimEvidenceRecord]: ...
    async def active_profile(self, subject_user_id: str) -> ProfileVersionRecord | None: ...
    async def write_profile_version(self, record: ProfileVersionRecord) -> None: ...
    async def publish_consolidation(
        self,
        record: ProfileVersionRecord | None,
        transitions: Sequence[ClaimTransitionRecord],
    ) -> None: ...
    async def record_recall(self, event: RecallEventWrite) -> None: ...
    async def cursor(self, source_name: str) -> ArchiveCursor | None: ...
    async def advance_cursor(self, cursor: ArchiveCursor) -> None: ...
    async def last_consolidated_at(self, subject_user_id: str) -> datetime | None: ...
    async def record_consolidated_at(
        self, subject_user_id: str, completed_at: datetime
    ) -> None: ...


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
        telemetry: RelationshipTelemetry | None = None,
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
        self.telemetry = telemetry or RelationshipTelemetry()

    async def observe_turn(self, observation: ObservationInput) -> ObservationResult:
        """Extract and persist one completed visible turn under its effective policy."""
        started = perf_counter()
        phases: dict[str, float] = {}
        policy_id: str | None = None
        try:
            phase = perf_counter()
            policy = await self._repository.active_policy_version()
            phases["policy"] = (perf_counter() - phase) * 1000
            policy_id = None if policy is None else policy.policy_version_id
            allowed = policy is not None and _visibility_allowed(
                policy.visibility_rules, observation.visibility_kind
            )
            if policy is None or not policy.relationship_learning_enabled or not allowed:
                result = ObservationResult("disabled", policy_id)
            else:
                relation = self._classify(observation)
                phase = perf_counter()
                try:
                    proposals = tuple(await self._extractor.extract(observation, relation))
                finally:
                    phases["extraction"] = (perf_counter() - phase) * 1000
                activated = 0
                phase = perf_counter()
                for proposal in proposals:
                    activated += await self._persist_proposal(observation, proposal, policy)
                phases["repository"] = (perf_counter() - phase) * 1000
                result = ObservationResult(
                    "observed", policy.policy_version_id, len(proposals), activated
                )
            fallback_reason = (
                next(
                    (
                        proposal.reason
                        for proposal in proposals
                        if proposal.reason.startswith("provider_fallback:")
                    ),
                    None,
                )
                if result.outcome == "observed"
                else None
            )
            self._emit_observation(result, observation.message_id, started, phases, fallback_reason)
            return result
        except Exception as error:
            self._emit_failure(
                "observation", observation.message_id, started, policy_id, error, phases
            )
            raise

    async def recall(self, envelope: ConversationEnvelope) -> MemoryRecall:
        """Retrieve scoped prompt memory and persist an idempotent content-free trace."""
        started = perf_counter()
        phases: dict[str, float] = {}
        policy_id: str | None = None
        try:
            phase = perf_counter()
            policy = await self._repository.active_policy_version()
            phases["policy"] = (perf_counter() - phase) * 1000
            policy_id = None if policy is None else policy.policy_version_id
            visibility = "guild" if envelope.guild_id else "direct_message"
            allowed = policy is not None and _visibility_allowed(
                policy.visibility_rules, visibility
            )
            if policy is None or not policy.relationship_learning_enabled or not allowed:
                recalled = MemoryRecall(relationship_retrieval=True)
                self._emit_recall(
                    recalled, envelope.message_id, started, policy_id, "disabled", phases
                )
                return recalled
            phase = perf_counter()
            try:
                recalled = await self._retriever.retrieve(envelope)
            finally:
                phases["ranking"] = (perf_counter() - phase) * 1000
            relation = self._classify(ObservationInput.from_envelope(envelope))
            phase = perf_counter()
            await self._repository.record_recall(
                RecallEventWrite(
                    recall_event_id=_stable_id(
                        "recall", policy.policy_version_id, envelope.message_id
                    ),
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
            phases["repository"] = (perf_counter() - phase) * 1000
            self._emit_recall(recalled, envelope.message_id, started, policy_id, None, phases)
            if policy.visibility_rules.get("shadow_mode", False):
                return replace(recalled, text="")
            return recalled
        except Exception as error:
            self._emit_failure("retrieval", envelope.message_id, started, policy_id, error, phases)
            raise

    async def consolidate_user(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> ConsolidationRun:
        """Promote full claim history and publish a profile only when content changes."""
        started = perf_counter()
        phases: dict[str, float] = {}
        policy_id: str | None = None
        try:
            phase = perf_counter()
            policy = await self._repository.active_policy_version()
            phases["policy"] = (perf_counter() - phase) * 1000
            policy_id = None if policy is None else policy.policy_version_id
            if policy is None or not policy.relationship_learning_enabled:
                run = ConsolidationRun(False, policy_id)
            else:
                phase = perf_counter()
                records = tuple(await self._repository.claims_for_subject(subject_user_id))
                evidence = tuple(
                    await self._repository.evidence_for_claims([item.claim_id for item in records])
                )
                active_profile = await self._repository.active_profile(subject_user_id)
                phases["repository_read"] = (perf_counter() - phase) * 1000
                now = self._clock()
                evidence_by_claim_id = _evidence_by_claim(records, evidence)
                predecessor = _predecessor_profile(
                    active_profile, records, evidence_by_claim_id, now
                )
                phase = perf_counter()
                result = self._consolidator.consolidate(
                    tuple(_relationship_claim(item) for item in records),
                    evidence_by_claim_id=evidence_by_claim_id,
                    predecessor=predecessor,
                    now=now,
                )
                phases["consolidation"] = (perf_counter() - phase) * 1000
                phase = perf_counter()
                run = await self._publish_profile(
                    subject_user_id, policy.policy_version_id, records, result
                )
                phases["publication"] = (perf_counter() - phase) * 1000
            phase = perf_counter()
            await self._repository.record_consolidated_at(subject_user_id, self._clock())
            phases["cadence"] = (perf_counter() - phase) * 1000
            self._emit_consolidation(run, subject_user_id, started, phases)
            return run
        except Exception as error:
            self._emit_failure("consolidation", subject_user_id, started, policy_id, error, phases)
            raise

    async def last_consolidated_at(self, subject_user_id: str) -> datetime | None:
        """Return the durable active-profile timestamp used by scheduler cadence."""
        return await self._repository.last_consolidated_at(subject_user_id)

    def _emit_observation(
        self,
        result: ObservationResult,
        correlation_id: str,
        started: float,
        phases: Mapping[str, float],
        fallback_reason: str | None,
    ) -> None:
        self.telemetry.emit(
            "observation",
            result.outcome,
            correlation_id=correlation_id,
            duration_ms=(perf_counter() - started) * 1000,
            candidate_count=result.candidate_count,
            selected_count=result.activated_count,
            rejected_count=result.candidate_count - result.activated_count,
            estimated_tokens=0,
            fallback_reason=fallback_reason,
            profile_changed=None,
            policy_version_id=result.policy_version_id,
            phase_durations_ms=phases,
        )

    def _emit_recall(
        self,
        recall: MemoryRecall,
        correlation_id: str,
        started: float,
        policy_version_id: str | None,
        fallback_reason: str | None,
        phases: Mapping[str, float],
    ) -> None:
        self.telemetry.emit(
            "retrieval",
            "recalled" if recall.selected_ids else "no_match",
            correlation_id=correlation_id,
            duration_ms=(perf_counter() - started) * 1000,
            candidate_count=len(recall.candidate_ids),
            selected_count=len(recall.selected_ids),
            rejected_count=len(recall.rejected_ids),
            estimated_tokens=recall.estimated_token_cost,
            fallback_reason=fallback_reason,
            profile_changed=None,
            policy_version_id=policy_version_id,
            phase_durations_ms=phases,
        )

    def _emit_consolidation(
        self,
        run: ConsolidationRun,
        correlation_id: str,
        started: float,
        phases: Mapping[str, float],
    ) -> None:
        self.telemetry.emit(
            "consolidation",
            "changed" if run.profile_changed else "no_op",
            correlation_id=correlation_id,
            duration_ms=(perf_counter() - started) * 1000,
            candidate_count=run.candidate_count,
            selected_count=int(run.profile_changed),
            rejected_count=int(run.rejected),
            estimated_tokens=0,
            fallback_reason="predecessor_rejected" if run.rejected else None,
            profile_changed=run.profile_changed,
            policy_version_id=run.policy_version_id,
            phase_durations_ms=phases,
        )

    def _emit_failure(
        self,
        operation: str,
        correlation_id: str,
        started: float,
        policy_version_id: str | None,
        error: Exception,
        phases: Mapping[str, float],
    ) -> None:
        self.telemetry.emit(
            operation,
            "failed",
            correlation_id=correlation_id,
            duration_ms=(perf_counter() - started) * 1000,
            candidate_count=0,
            selected_count=0,
            rejected_count=0,
            estimated_tokens=0,
            fallback_reason=type(error).__name__,
            profile_changed=None,
            policy_version_id=policy_version_id,
            phase_durations_ms=phases,
        )

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

    async def _publish_profile(
        self,
        subject_user_id: str,
        policy_version_id: str,
        records: Sequence[ClaimRecord],
        result: ConsolidationResult,
    ) -> ConsolidationRun:
        profile = result.profile
        active = await self._repository.active_profile(subject_user_id)
        claim_links = () if profile is None else _profile_claim_links(profile)
        unchanged = (
            profile is not None
            and active is not None
            and (
                active.index_text,
                active.overview_text,
                active.policy_version_id,
                tuple(sorted(active.claim_links, key=_profile_link_key)),
            )
            == (
                profile.index_text,
                profile.overview_text,
                policy_version_id,
                tuple(sorted(claim_links, key=_profile_link_key)),
            )
        )
        record = None
        if profile is not None and not unchanged:
            version_id = _stable_id(
                "profile",
                subject_user_id,
                policy_version_id,
                profile.index_text,
                profile.overview_text,
                *(f"{link.layer}:{link.position}:{link.claim_id}" for link in claim_links),
            )
            record = ProfileVersionRecord(
                version_id,
                subject_user_id,
                profile.index_text,
                profile.overview_text,
                "relationship-profile-v1",
                "deterministic-v1",
                policy_version_id,
                self._clock(),
                claim_links,
            )
        transitions = _claim_transitions(records, result.claims, self._clock())
        await self._repository.publish_consolidation(record, transitions)
        profile_version_id = (
            record.profile_version_id
            if record is not None
            else None
            if active is None
            else active.profile_version_id
        )
        return ConsolidationRun(
            record is not None,
            policy_version_id,
            profile_version_id,
            len(result.claims),
            result.rejected,
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


def _claim_transitions(
    records: Sequence[ClaimRecord],
    claims: Sequence[RelationshipClaim],
    transitioned_at: datetime,
) -> tuple[ClaimTransitionRecord, ...]:
    prior = {item.claim_id: item.state for item in records}
    return tuple(
        ClaimTransitionRecord(claim.claim_id, previous, claim.state, transitioned_at)
        for claim in claims
        if (previous := prior.get(claim.claim_id)) is not None and previous != claim.state
    )


def _relationship_profile(
    record: ProfileVersionRecord, claims: Sequence[ClaimRecord]
) -> RelationshipProfile:
    by_id = {claim.claim_id: claim for claim in claims}
    grouped: dict[tuple[str, int], list[ClaimRecord]] = defaultdict(list)
    for link in record.claim_links:
        claim = by_id.get(link.claim_id)
        if claim is None:
            raise ValueError("active relationship profile references an unknown claim")
        grouped[(link.layer, link.position)].append(claim)
    entries: dict[str, list[tuple[int, ProfileEntry]]] = defaultdict(list)
    for (layer, position), items in grouped.items():
        keys = {" ".join(item.key.casefold().split()) for item in items}
        values = {" ".join(item.value.split()) for item in items}
        if len(keys) != 1 or len(values) != 1:
            raise ValueError("active relationship profile claim group is inconsistent")
        entries[layer].append(
            (
                position,
                ProfileEntry(
                    next(iter(keys)),
                    next(iter(values)),
                    tuple(sorted(item.claim_id for item in items)),
                ),
            )
        )
    profile = RelationshipProfile(
        subject_user_id=record.subject_user_id,
        version=1,
        posture=_ordered_entries(entries["posture"]),
        expression=_ordered_entries(entries["expression"]),
        interests=_ordered_entries(entries["interests"]),
        care_patterns=_ordered_entries(entries["care_patterns"]),
        conflict_repair=_ordered_entries(entries["conflict_repair"]),
        anchors=_ordered_entries(entries["anchors"]),
    )
    if (profile.index_text, profile.overview_text) != (record.index_text, record.overview_text):
        raise ValueError("active relationship profile content does not match its claim links")
    return profile


def _predecessor_profile(
    record: ProfileVersionRecord | None,
    claims: Sequence[ClaimRecord],
    evidence_by_claim_id: Mapping[str, Sequence[EvidenceProposal]],
    now: datetime,
) -> RelationshipProfile | None:
    if record is None:
        return None
    if record.claim_links or not (record.index_text.strip() or record.overview_text.strip()):
        return _relationship_profile(record, claims)
    rebuilt = (
        RelationshipConsolidator()
        .consolidate(
            tuple(_relationship_claim(claim) for claim in claims),
            evidence_by_claim_id=evidence_by_claim_id,
            now=now,
        )
        .profile
    )
    if rebuilt is None or (rebuilt.index_text, rebuilt.overview_text) != (
        record.index_text,
        record.overview_text,
    ):
        raise ValueError("legacy relationship profile cannot be reconstructed from claim history")
    return rebuilt


def _profile_claim_links(profile: RelationshipProfile) -> tuple[ProfileClaimLinkRecord, ...]:
    layers = (
        ("posture", profile.posture),
        ("expression", profile.expression),
        ("interests", profile.interests),
        ("care_patterns", profile.care_patterns),
        ("conflict_repair", profile.conflict_repair),
        ("anchors", profile.anchors),
    )
    return tuple(
        ProfileClaimLinkRecord(claim_id, layer, position)
        for layer, layer_entries in layers
        for position, entry in enumerate(layer_entries)
        for claim_id in entry.claim_ids
    )


def _profile_link_key(link: ProfileClaimLinkRecord) -> tuple[str, int, str]:
    return (link.layer, link.position, link.claim_id)


def _ordered_entries(entries: Sequence[tuple[int, ProfileEntry]]) -> tuple[ProfileEntry, ...]:
    return tuple(entry for _, entry in sorted(entries, key=lambda item: item[0]))


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


def _visibility_allowed(rules: Mapping[str, bool], visibility_kind: str) -> bool:
    """Preserve legacy policies while enforcing explicit runtime scope switches."""
    return rules.get(visibility_kind, True)
