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
        sink_timeout_seconds: float = 1.0,
        close_timeout_seconds: float = 5.0,
    ) -> None:
        if capacity < 1:
            raise ValueError("telemetry capacity must be positive")
        if sink_timeout_seconds <= 0:
            raise ValueError("telemetry sink timeout must be positive")
        if close_timeout_seconds <= 0:
            raise ValueError("telemetry close timeout must be positive")
        self._records: deque[RelationshipOperationRecord] = deque(maxlen=capacity)
        self._sink = sink
        self._sink_timeout_seconds = sink_timeout_seconds
        self._close_timeout_seconds = close_timeout_seconds
        self._queue: asyncio.Queue[RelationshipOperationRecord] = asyncio.Queue(maxsize=capacity)
        self._worker: asyncio.Task[None] | None = None
        self.last_sink_failure: str | None = None
        self._dropped_sink_records = 0
        self._pending_sink_records = 0
        self._active_record: RelationshipOperationRecord | None = None

    @property
    def records(self) -> tuple[RelationshipOperationRecord, ...]:
        """Return an immutable snapshot for health aggregation."""
        return tuple(self._records)

    @property
    def dropped_sink_records(self) -> int:
        """Number of durable telemetry writes abandoned after bounded attempts."""
        return self._dropped_sink_records

    @property
    def pending_sink_records(self) -> int:
        """Number of durable writes still awaiting queue accounting."""
        return self._pending_sink_records

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
                self._pending_sink_records += 1
            except asyncio.QueueFull:
                self.last_sink_failure = "telemetry_queue_full"
                return
            if self._worker is None or self._worker.done():
                self._worker = asyncio.create_task(self._run_sink(), name="relationship-telemetry")

    async def flush(self) -> None:
        """Await pending durable writes without exposing their payloads."""
        try:
            await asyncio.wait_for(self._queue.join(), timeout=self._close_timeout_seconds)
        except TimeoutError:
            self.last_sink_failure = "telemetry_flush_timeout"

    async def close(self) -> None:
        """Flush writes and stop the owned sink worker."""
        await self.flush()
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.cancel()
            done, _ = await asyncio.wait({worker}, timeout=self._close_timeout_seconds)
            if worker in done:
                with contextlib.suppress(asyncio.CancelledError):
                    worker.result()
            else:
                self.last_sink_failure = "telemetry_close_timeout"
                if self._active_record is not None:
                    self._dropped_sink_records += 1
                    self._pending_sink_records -= 1
                    self._queue.task_done()
                    self._active_record = None
        while True:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            self._dropped_sink_records += 1
            self._pending_sink_records -= 1
            self._queue.task_done()

    async def _run_sink(self) -> None:
        assert self._sink is not None
        while True:
            record = await self._queue.get()
            self._active_record = record
            try:
                retry_count = 3
                for attempt in range(retry_count):
                    try:
                        await self._invoke_sink_bounded(record)
                        self.last_sink_failure = None
                        break
                    except asyncio.CancelledError:
                        self._dropped_sink_records += 1
                        raise
                    except Exception as error:
                        self.last_sink_failure = type(error).__name__
                        if attempt < retry_count - 1:
                            await asyncio.sleep(0)
                else:
                    self._dropped_sink_records += 1
            finally:
                if self._active_record is record:
                    self._pending_sink_records -= 1
                    self._queue.task_done()
                    self._active_record = None

    async def _invoke_sink_bounded(self, record: RelationshipOperationRecord) -> None:
        """Run an untrusted sink with a hard application-shutdown boundary.

        An arbitrary coroutine can catch ``CancelledError`` forever.  Keeping such
        a coroutine on the application loop would make ``asyncio.run`` wait for it
        during shutdown. Normal sinks retain the caller's event loop and resources;
        only an already-cancelled sink that exceeds its deadline is abandoned.
        """
        assert self._sink is not None

        async def invoke() -> None:
            assert self._sink is not None
            await self._sink(record)

        sink_task: asyncio.Task[None] = asyncio.create_task(
            invoke(), name="relationship-telemetry-write"
        )
        try:
            done, _ = await asyncio.wait({sink_task}, timeout=self._sink_timeout_seconds)
            if sink_task not in done:
                sink_task.cancel()
                self._abandon_if_cancellation_is_suppressed(sink_task)
                raise TimeoutError("telemetry sink timed out")
            sink_task.result()
        except asyncio.CancelledError:
            sink_task.cancel()
            self._abandon_if_cancellation_is_suppressed(sink_task)
            raise

    @staticmethod
    def _abandon_if_cancellation_is_suppressed(task: asyncio.Task[None]) -> None:
        """Keep a hostile sink from participating in runner shutdown.

        CPython's runner waits for every registered task after cancelling it. A
        sink that deliberately suppresses cancellation would therefore hold the
        entire process open. Removing only that already-cancelled untrusted task
        gives telemetry a hard abandonment boundary while normal sinks retain
        their caller's event loop and resources.
        """
        if task.done():
            return
        scheduled_tasks = getattr(asyncio.tasks, "_scheduled_tasks", None)
        if scheduled_tasks is not None:
            scheduled_tasks.discard(task)
        task._log_destroy_pending = False  # type: ignore[attr-defined]
