"""Content-free runtime telemetry for relationship-memory operations."""

from __future__ import annotations

import asyncio
import hashlib
from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime


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
    created_at: datetime


class RelationshipTelemetry:
    """Retain a bounded process-local window of privacy-safe operation records."""

    def __init__(
        self,
        *,
        capacity: int = 1000,
        sink: Callable[[RelationshipOperationRecord], Awaitable[None]] | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("telemetry capacity must be positive")
        self._records: deque[RelationshipOperationRecord] = deque(maxlen=capacity)
        self._sink = sink
        self._pending: set[asyncio.Future[None]] = set()

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
        record = RelationshipOperationRecord(
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
            datetime.now(UTC),
        )
        self._records.append(record)
        if self._sink is not None:
            task = asyncio.ensure_future(self._sink(record))
            self._pending.add(task)
            task.add_done_callback(self._pending.discard)

    async def flush(self) -> None:
        """Await pending durable writes without exposing their payloads."""
        if self._pending:
            await asyncio.gather(*tuple(self._pending), return_exceptions=True)
