"""Content-free runtime telemetry for relationship-memory operations."""

from __future__ import annotations

import hashlib
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RelationshipOperationRecord:
    """One bounded operation outcome without conversation or profile content."""

    operation: str
    outcome: str
    correlation_hash: str
    duration_ms: float
    candidate_count: int
    selected_count: int
    rejected_count: int
    estimated_tokens: int
    fallback_reason: str | None
    profile_changed: bool | None
    policy_version_id: str | None
    phase_durations_ms: Mapping[str, float]


class RelationshipTelemetry:
    """Retain a bounded process-local window of privacy-safe operation records."""

    def __init__(self, *, capacity: int = 1000) -> None:
        if capacity < 1:
            raise ValueError("telemetry capacity must be positive")
        self._records: deque[RelationshipOperationRecord] = deque(maxlen=capacity)

    @property
    def records(self) -> tuple[RelationshipOperationRecord, ...]:
        """Return an immutable snapshot for health aggregation."""
        return tuple(self._records)

    def emit(
        self,
        operation: str,
        outcome: str,
        *,
        correlation_id: str,
        duration_ms: float,
        candidate_count: int,
        selected_count: int,
        rejected_count: int,
        estimated_tokens: int,
        fallback_reason: str | None,
        profile_changed: bool | None,
        policy_version_id: str | None,
        phase_durations_ms: Mapping[str, float] | None = None,
    ) -> None:
        """Record only bounded counts, timing, status, and a hashed correlation ID."""
        digest = hashlib.sha256(correlation_id.encode()).hexdigest()
        self._records.append(
            RelationshipOperationRecord(
                operation,
                outcome,
                f"sha256:{digest}",
                max(0.0, duration_ms),
                max(0, candidate_count),
                max(0, selected_count),
                max(0, rejected_count),
                max(0, estimated_tokens),
                fallback_reason,
                profile_changed,
                policy_version_id,
                {
                    key: max(0.0, value)
                    for key, value in (phase_durations_ms or {operation: duration_ms}).items()
                },
            )
        )
