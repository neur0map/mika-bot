"""Content-free telemetry emission for relationship-memory operations."""

from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter

from mika.conversation.context.retrieval import MemoryRecall
from mika.conversation.relationships.service_contracts import ConsolidationRun, ObservationResult
from mika.conversation.relationships.telemetry import RelationshipTelemetry


class RelationshipServiceTelemetry:
    """Emit bounded operation metadata without message or memory content."""

    telemetry: RelationshipTelemetry

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
