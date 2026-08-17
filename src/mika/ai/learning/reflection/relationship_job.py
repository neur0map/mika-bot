"""Bounded background processing for completed relationship observations."""

from __future__ import annotations

import asyncio
import contextlib
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol

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

    async def last_consolidated_at(self, subject_user_id: str) -> datetime | None: ...


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
        self.telemetry = telemetry or RelationshipTelemetry()
        self._task: asyncio.Task[None] | None = None
        self.last_failure: str | None = None

    @property
    def running(self) -> bool:
        """Whether the worker task is active."""
        return self._task is not None and not self._task.done()

    def start(self, wait_until_ready: Callable[[], Awaitable[None]]) -> None:
        """Start one worker gated on Discord readiness."""
        if not self._enabled or self.running:
            return
        self._task = asyncio.create_task(
            self._run(wait_until_ready), name="relationship-observation"
        )

    def submit(self, envelope: ConversationEnvelope) -> bool:
        """Enqueue one immutable observation without awaiting extraction."""
        if not self._enabled:
            return False
        try:
            self._queue.put_nowait(ObservationInput.from_envelope(envelope))
        except asyncio.QueueFull:
            if len(self._overflow) == self._overflow.maxlen:
                logger.warning(
                    "relationship observation buffers full; turn remains in local memory"
                )
                self._emit_queue(envelope.message_id, "rejected", "buffers_full")
                return False
            self._overflow.append(ObservationInput.from_envelope(envelope))
            self._emit_queue(envelope.message_id, "deferred", "buffer_deferred")
        return True

    async def close(self) -> None:
        """Cancel and await the owned worker before application shutdown."""
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _run(self, wait_until_ready: Callable[[], Awaitable[None]]) -> None:
        await wait_until_ready()
        while True:
            observation = await self._queue.get()
            try:
                await self._observe_with_retry(observation)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.last_failure = type(error).__name__
                logger.warning("relationship observation failed: %s", self.last_failure)
            finally:
                self._queue.task_done()
                if self._overflow and not self._queue.full():
                    self._queue.put_nowait(self._overflow.popleft())

    async def _observe_with_retry(self, observation: ObservationInput) -> None:
        for attempt in range(self._retry_limit + 1):
            try:
                await self._service.observe_turn(observation)
                await self._consolidate_if_due(observation)
                return
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.last_failure = type(error).__name__
                if attempt == self._retry_limit:
                    logger.warning("relationship observation failed: %s", self.last_failure)
                    return
                self._emit_queue(observation.message_id, "retry", f"{self.last_failure}:retry")

    async def _consolidate_if_due(self, observation: ObservationInput) -> None:
        previous = await self._service.last_consolidated_at(observation.subject_user_id)
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
