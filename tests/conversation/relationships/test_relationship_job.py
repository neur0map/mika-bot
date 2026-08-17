"""Bounded relationship observation job lifecycle."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from mika.ai.learning.reflection.relationship_job import RelationshipObservationJob
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.relationships.service import ObservationInput, ObservationResult


class Service:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.processed = asyncio.Event()
        self.third_call = asyncio.Event()
        self.fourth_call = asyncio.Event()
        self.last_consolidation = datetime.now(UTC)
        self.consolidated: list[str] = []
        self.consolidated_event = asyncio.Event()

    async def observe_turn(self, observation: ObservationInput) -> ObservationResult:
        self.calls.append(observation.message_id)
        self.processed.set()
        if len(self.calls) >= 3:
            self.third_call.set()
        if len(self.calls) >= 4:
            self.fourth_call.set()
        if observation.message_id == "fails":
            raise RuntimeError("provider unavailable")
        return ObservationResult("observed", "policy-1")

    async def last_consolidated_at(self, subject_user_id: str) -> datetime | None:
        return self.last_consolidation

    async def consolidate_user(self, subject_user_id: str, **scope: str | None) -> object:
        self.consolidated.append(subject_user_id)
        self.last_consolidation = datetime.now(UTC)
        self.consolidated_event.set()
        return object()


def envelope(message_id: str) -> ConversationEnvelope:
    return ConversationEnvelope(
        message_id,
        "channel-1",
        "guild-1",
        "user-1",
        "Ada",
        "I like Hades",
        False,
        datetime.now(UTC),
    )


async def test_job_is_bounded_survives_extraction_failure_and_shuts_down() -> None:
    service = Service()
    ready = asyncio.Event()
    job = RelationshipObservationJob(service, max_queue_size=1)
    job.start(ready.wait)

    assert job.submit(envelope("fails")) is True
    assert job.submit(envelope("queue-full")) is True
    assert job.submit(envelope("buffers-full")) is False

    ready.set()
    await asyncio.wait_for(service.processed.wait(), timeout=1)
    await asyncio.wait_for(service.third_call.wait(), timeout=1)
    assert job.submit(envelope("continues")) is True

    await asyncio.wait_for(service.fourth_call.wait(), timeout=1)
    assert service.calls == ["fails", "fails", "queue-full", "continues"]
    assert job.last_failure == "RuntimeError"
    assert {record.fallback_reason for record in job.telemetry.records} >= {
        "buffer_deferred",
        "buffers_full",
        "RuntimeError:retry",
    }

    await job.close()

    assert job.running is False


async def test_consolidation_due_state_comes_from_durable_service_timestamp() -> None:
    service = Service()
    service.last_consolidation = datetime(2020, 1, 1, tzinfo=UTC)
    job = RelationshipObservationJob(service, max_queue_size=1)
    ready = asyncio.Event()
    ready.set()
    job.start(ready.wait)

    assert job.submit(envelope("due")) is True
    await asyncio.wait_for(service.consolidated_event.wait(), timeout=1)

    await job.close()
    assert service.consolidated == ["user-1"]


async def test_disabled_job_rejects_observations_without_calling_service() -> None:
    service = Service()
    job = RelationshipObservationJob(service, max_queue_size=1, enabled=False)

    assert job.submit(envelope("disabled")) is False
    assert service.calls == []
