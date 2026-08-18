"""Orchestrate evidence-backed relationship observation, recall, and consolidation."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from time import perf_counter

from mika.conversation.context.retrieval import MemoryRecall
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.relationships.activation import ActivationPolicy
from mika.conversation.relationships.consolidation import (
    ConsolidationResult,
    RelationshipConsolidator,
)
from mika.conversation.relationships.contracts import RelationDecision
from mika.conversation.relationships.extraction import EvidenceProposal
from mika.conversation.relationships.service_contracts import (
    ConsolidationRun,
    EvidenceExtractor,
    ObservationInput,
    ObservationResult,
    PendingObservationResult,
    PendingObservationSource,
    RelationClassifier,
    RelationshipRepository,
    RelationshipRetriever,
)
from mika.conversation.relationships.service_mapping import (
    _claim_id,
    _claim_in_scope,
    _claim_transitions,
    _claim_write,
    _correction_predecessor,
    _effective_archive_observation,
    _evidence_by_claim,
    _evidence_write,
    _physical_archive_visibility,
    _predecessor_profile,
    _profile_claim_links,
    _profile_link_key,
    _proposal_from_record,
    _relationship_claim,
    _stable_id,
    _visibility_allowed,
)
from mika.conversation.relationships.service_telemetry import RelationshipServiceTelemetry
from mika.conversation.relationships.telemetry import RelationshipTelemetry
from mika.persistence.conversations.relationship_records import (
    ArchiveCursor,
    ArchiveSourceRecord,
    ClaimRecord,
    ProfileVersionRecord,
    RecallEventWrite,
    RelationshipMemoryPolicyVersionRecord,
)

__all__ = [
    "ConsolidationRun",
    "ObservationInput",
    "ObservationResult",
    "PendingObservationResult",
    "RelationshipMemoryService",
]


class RelationshipMemoryService(RelationshipServiceTelemetry):
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

    async def observe_archive_candidate(self, source: ArchiveSourceRecord) -> ObservationResult:
        """Persist historical evidence as candidates for later consolidation."""
        policy = await self._repository.active_policy_version()
        if policy is None or not policy.relationship_learning_enabled:
            policy_id = None if policy is None else policy.policy_version_id
            return ObservationResult("disabled", policy_id)
        observation = ObservationInput.from_archive(source)
        physical_visibility = _physical_archive_visibility(source)
        if not _visibility_allowed(policy.visibility_rules, physical_visibility):
            return ObservationResult("disabled", policy.policy_version_id)
        relation = self._classify(observation)
        proposals = tuple(await self._extractor.extract(observation, relation))
        for proposal in proposals:
            effective = _effective_archive_observation(source, observation, proposal)
            if _visibility_allowed(policy.visibility_rules, effective.visibility_kind):
                await self._persist_proposal(effective, proposal, policy, activate=False)
        return ObservationResult("observed", policy.policy_version_id, len(proposals), 0)

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
                records = tuple(
                    item
                    for item in await self._repository.claims_for_subject(subject_user_id)
                    if _claim_in_scope(item, visibility_kind, guild_id, channel_id)
                )
                evidence = tuple(
                    await self._repository.evidence_for_claims([item.claim_id for item in records])
                )
                active_profile = await self._repository.active_profile_for_scope(
                    subject_user_id,
                    visibility_kind=visibility_kind,
                    guild_id=guild_id,
                    channel_id=channel_id,
                )
                phases["repository_read"] = (perf_counter() - phase) * 1000
                now = self._clock()
                evidence_by_claim_id = _evidence_by_claim(records, evidence)
                claim_ids = {item.claim_id for item in records}
                profile_is_scope_complete = bool(
                    active_profile
                    and active_profile.claim_links
                    and all(link.claim_id in claim_ids for link in active_profile.claim_links)
                )
                predecessor = (
                    _predecessor_profile(active_profile, records, evidence_by_claim_id, now)
                    if profile_is_scope_complete
                    else None
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
                    subject_user_id,
                    policy.policy_version_id,
                    records,
                    result,
                    compatible_active_profile=(
                        active_profile if profile_is_scope_complete else None
                    ),
                    visibility_kind=visibility_kind,
                    guild_id=guild_id,
                    channel_id=channel_id,
                )
                phases["publication"] = (perf_counter() - phase) * 1000
            phase = perf_counter()
            await self._repository.record_scoped_consolidated_at(
                subject_user_id,
                self._clock(),
                visibility_kind=visibility_kind,
                guild_id=guild_id,
                channel_id=channel_id,
            )
            phases["cadence"] = (perf_counter() - phase) * 1000
            self._emit_consolidation(run, subject_user_id, started, phases)
            return run
        except Exception as error:
            self._emit_failure("consolidation", subject_user_id, started, policy_id, error, phases)
            raise

    async def last_consolidated_at(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str | None = None,
        guild_id: str | None = None,
        channel_id: str | None = None,
    ) -> datetime | None:
        """Return the durable active-profile timestamp used by scheduler cadence."""
        if visibility_kind is not None:
            return await self._repository.scoped_last_consolidated_at(
                subject_user_id,
                visibility_kind=visibility_kind,
                guild_id=guild_id,
                channel_id=channel_id,
            )
        return await self._repository.last_consolidated_at(subject_user_id)

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
        *,
        activate: bool = True,
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
        if not activate:
            return 0
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
        *,
        compatible_active_profile: ProfileVersionRecord | None = None,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> ConsolidationRun:
        profile = result.profile
        active = compatible_active_profile
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
                visibility_kind,
                guild_id or "",
                channel_id or "",
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
                visibility_kind,
                guild_id,
                channel_id,
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
