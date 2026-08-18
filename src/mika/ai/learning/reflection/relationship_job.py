"""Bounded background processing for completed relationship observations."""

from __future__ import annotations

import asyncio
import contextlib
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from mika.ai.learning.reflection.relationship_spool import RelationshipObservationSpool
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.relationships.service import ObservationInput, ObservationResult
from mika.conversation.relationships.telemetry import RelationshipTelemetry
from mika.core.logging import get_logger

logger = get_logger(__name__)


class RelationshipObservationService(Protocol):
    """Service capabilities consumed by the background worker."""

    async def observe_turn(self, observation: ObservationInput) -> ObservationResult: ...

    async def consolidate_user(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> object: ...

    async def last_consolidated_at(
        self,
        subject_user_id: str,
        *,
        visibility_kind: str,
        guild_id: str | None,
        channel_id: str | None,
    ) -> datetime | None: ...

    async def run_pending_observations(self, *, limit: int | None = None) -> object: ...


class RelationshipObservationJob:
    """Queue relationship extraction without delaying visible Discord actions."""

    def __init__(
        self,
        service: RelationshipObservationService,
        *,
        max_queue_size: int,
        enabled: bool = True,
        consolidation_interval_seconds: float = 604_800.0,
        retry_limit: int = 1,
        retry_backoff_seconds: float = 0.05,
        recovery_attempt_limit: int = 5,
        shutdown_timeout_seconds: float = 10.0,
        spool_path: Path | None = None,
        spool_ttl_seconds: float = 86_400.0,
        telemetry: RelationshipTelemetry | None = None,
    ) -> None:
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be positive")
        if consolidation_interval_seconds <= 0:
            raise ValueError("consolidation_interval_seconds must be positive")
        if retry_limit < 0:
            raise ValueError("retry_limit cannot be negative")
        self._service = service
        self._queue: asyncio.Queue[ObservationInput] = asyncio.Queue(max_queue_size)
        self._overflow: deque[ObservationInput] = deque(maxlen=max_queue_size)
        self._enabled = enabled
        self._consolidation_interval_seconds = consolidation_interval_seconds
        self._retry_limit = retry_limit
        self._retry_backoff_seconds = retry_backoff_seconds
        self._recovery_attempt_limit = recovery_attempt_limit
        self._shutdown_timeout_seconds = shutdown_timeout_seconds
        self._spool = (
            None
            if spool_path is None
            else RelationshipObservationSpool(spool_path, ttl_seconds=spool_ttl_seconds)
        )
        self._queued_ids: set[str] = set()
        self.telemetry = telemetry or RelationshipTelemetry()
        self._task: asyncio.Task[None] | None = None
        self.last_failure: str | None = None
        self._live_since_archive = 0

    @property
    def running(self) -> bool:
        """Whether the worker task is active."""
        return self._task is not None and not self._task.done()

    def start(self, wait_until_ready: Callable[[], Awaitable[None]]) -> None:
        """Start one worker gated on Discord readiness."""
        if not self._enabled or self.running:
            return
        self._replenish_from_spool()
        self._task = asyncio.create_task(
            self._run(wait_until_ready), name="relationship-observation"
        )

    def submit(self, envelope: ConversationEnvelope) -> bool:
        """Enqueue one immutable observation without awaiting extraction."""
        if not self._enabled:
            return False
        observation = ObservationInput.from_envelope(envelope)
        if self._spool is not None:
            self._spool.put(observation)
        try:
            self._queue.put_nowait(observation)
            self._queued_ids.add(observation.message_id)
        except asyncio.QueueFull:
            if len(self._overflow) == self._overflow.maxlen:
                if self._spool is not None:
                    self._emit_queue(envelope.message_id, "deferred", "durable_spool")
                    return True
                logger.warning(
                    "relationship observation buffers full; turn remains in local memory"
                )
                self._emit_queue(envelope.message_id, "rejected", "buffers_full")
                if self._spool is not None:
                    self._spool.complete(observation.message_id)
                return False
            self._overflow.append(observation)
            self._queued_ids.add(observation.message_id)
            self._emit_queue(envelope.message_id, "deferred", "buffer_deferred")
        return True

    async def close(self) -> None:
        """Cancel and await the owned worker before application shutdown."""
        task = self._task
        self._task = None
        if task is None:
            return
        try:
            await asyncio.wait_for(self._queue.join(), timeout=self._shutdown_timeout_seconds)
        except TimeoutError:
            logger.warning("relationship observation shutdown drain timed out")
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _run(self, wait_until_ready: Callable[[], Awaitable[None]]) -> None:
        await wait_until_ready()
        while True:
            try:
                observation = await asyncio.wait_for(self._queue.get(), timeout=0.25)
            except TimeoutError:
                await self._run_pending_archive()
                self._replenish_from_spool()
                continue
            try:
                await self._observe_with_retry(observation)
                self._live_since_archive += 1
                if self._live_since_archive >= self._queue.maxsize:
                    await self._run_pending_archive()
                    self._live_since_archive = 0
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.last_failure = type(error).__name__
                logger.warning("relationship observation failed: %s", self.last_failure)
            finally:
                self._queue.task_done()
                self._queued_ids.discard(observation.message_id)
                if self._overflow and not self._queue.full():
                    deferred = self._overflow.popleft()
                    self._queue.put_nowait(deferred)
                    self._queued_ids.add(deferred.message_id)
                self._replenish_from_spool()

    async def _run_pending_archive(self) -> None:
        runner = getattr(self._service, "run_pending_observations", None)
        if runner is None:
            return
        try:
            await runner(limit=self._queue.maxsize)
        except Exception as error:
            self.last_failure = type(error).__name__
            logger.warning("relationship archive observation failed: %s", self.last_failure)

    async def _observe_with_retry(self, observation: ObservationInput) -> None:
        for attempt in range(self._retry_limit + 1):
            try:
                await self._service.observe_turn(observation)
                await self._consolidate_if_due(observation)
                if self._spool is not None:
                    self._spool.complete(observation.message_id)
                return
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.last_failure = type(error).__name__
                if attempt == self._retry_limit:
                    if self._spool is not None:
                        dead_letter = self._spool.fail(
                            observation.message_id,
                            self.last_failure,
                            max_attempts=self._recovery_attempt_limit,
                            backoff_seconds=self._retry_backoff_seconds,
                        )
                        if dead_letter:
                            self._emit_queue(
                                observation.message_id, "dead_letter", self.last_failure
                            )
                    logger.warning("relationship observation failed: %s", self.last_failure)
                    return
                self._emit_queue(observation.message_id, "retry", f"{self.last_failure}:retry")
                await asyncio.sleep(self._retry_backoff_seconds * (2**attempt))

    def _replenish_from_spool(self) -> None:
        if self._spool is None:
            return
        available = self._queue.maxsize - self._queue.qsize()
        for observation in self._spool.pending(available, excluding=frozenset(self._queued_ids)):
            self._queue.put_nowait(observation)
            self._queued_ids.add(observation.message_id)

    async def _consolidate_if_due(self, observation: ObservationInput) -> None:
        previous = await self._service.last_consolidated_at(
            observation.subject_user_id,
            visibility_kind=observation.visibility_kind,
            guild_id=observation.guild_id,
            channel_id=observation.channel_id,
        )
        now = datetime.now(UTC)
        if previous is not None and (now - previous).total_seconds() < (
            self._consolidation_interval_seconds
        ):
            return
        await self._service.consolidate_user(
            observation.subject_user_id,
            visibility_kind=observation.visibility_kind,
            guild_id=observation.guild_id,
            channel_id=observation.channel_id,
        )

    def _emit_queue(self, correlation_id: str, outcome: str, reason: str) -> None:
        self.telemetry.emit(
            "observation_queue",
            outcome,
            correlation_id=correlation_id,
            duration_ms=0.0,
            candidate_count=0,
            selected_count=0,
            rejected_count=int(outcome == "rejected"),
            estimated_tokens=0,
            fallback_reason=reason,
            profile_changed=None,
            policy_version_id=None,
            phase_durations_ms={"queue": 0.0},
        )
