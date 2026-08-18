"""Content-free runtime telemetry for relationship-memory operations."""

from __future__ import annotations

import asyncio
import contextlib
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
        self._queue: asyncio.Queue[RelationshipOperationRecord] = asyncio.Queue(maxsize=capacity)
        self._worker: asyncio.Task[None] | None = None
        self.last_sink_failure: str | None = None

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
            try:
                self._queue.put_nowait(record)
            except asyncio.QueueFull:
                self.last_sink_failure = "telemetry_queue_full"
                return
            if self._worker is None or self._worker.done():
                self._worker = asyncio.create_task(self._run_sink(), name="relationship-telemetry")

    async def flush(self) -> None:
        """Await pending durable writes without exposing their payloads."""
        await self._queue.join()

    async def close(self) -> None:
        """Flush writes and stop the owned sink worker."""
        await self.flush()
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker

    async def _run_sink(self) -> None:
        assert self._sink is not None
        while True:
            record = await self._queue.get()
            try:
                retry_count = 3
                for attempt in range(retry_count):
                    try:
                        await self._sink(record)
                        self.last_sink_failure = None
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as error:
                        self.last_sink_failure = type(error).__name__
                        if attempt < retry_count - 1:
                            await asyncio.sleep(0)
            finally:
                self._queue.task_done()
