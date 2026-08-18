"""Bounded relationship observation job lifecycle."""

from __future__ import annotations

import asyncio
import sqlite3
import stat
import time
from datetime import UTC, datetime
from pathlib import Path

from mika.ai.learning.reflection.relationship_job import RelationshipObservationJob
from mika.ai.learning.reflection.relationship_spool import RelationshipObservationSpool
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


class RecoveredService(Service):
    def __init__(self, expected_calls: int = 1) -> None:
        super().__init__()
        self.expected_calls = expected_calls
        self.all_processed = asyncio.Event()

    async def observe_turn(self, observation: ObservationInput) -> ObservationResult:
        self.calls.append(observation.message_id)
        self.processed.set()
        if len(self.calls) >= self.expected_calls:
            self.all_processed.set()
        return ObservationResult("observed", "policy-1")


class ArchiveService(RecoveredService):
    def __init__(self) -> None:
        super().__init__()
        self.archive_batches = 0
        self.archive_processed = asyncio.Event()

    async def run_pending_observations(self, *, limit: int | None = None) -> object:
        del limit
        self.archive_batches += 1
        self.archive_processed.set()
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


async def test_shutdown_drains_accepted_observations(tmp_path: Path) -> None:
    service = Service()
    ready = asyncio.Event()
    ready.set()
    job = RelationshipObservationJob(
        service, max_queue_size=2, spool_path=tmp_path / "observations.sqlite3"
    )
    job.start(ready.wait)
    assert job.submit(envelope("one"))
    assert job.submit(envelope("two"))

    await job.close()

    assert service.calls == ["one", "two"]


async def test_failed_observation_is_recovered_after_restart(tmp_path: Path) -> None:
    spool = tmp_path / "observations.sqlite3"
    failing = Service()
    first = RelationshipObservationJob(failing, max_queue_size=2, retry_limit=0, spool_path=spool)
    assert first.submit(envelope("fails"))
    ready = asyncio.Event()
    ready.set()
    first.start(ready.wait)
    await asyncio.wait_for(failing.processed.wait(), timeout=1)
    await first.close()

    recovered = RecoveredService()
    second = RelationshipObservationJob(recovered, max_queue_size=2, spool_path=spool)
    second.start(ready.wait)
    await asyncio.wait_for(recovered.processed.wait(), timeout=1)
    await second.close()

    assert recovered.calls == ["fails"]


async def test_exhausted_recovery_is_visible_as_dead_letter(tmp_path: Path) -> None:
    service = Service()
    ready = asyncio.Event()
    ready.set()
    job = RelationshipObservationJob(
        service,
        max_queue_size=1,
        retry_limit=0,
        recovery_attempt_limit=1,
        spool_path=tmp_path / "observations.sqlite3",
    )
    assert job.submit(envelope("fails"))
    job.start(ready.wait)

    await job.close()

    assert any(record.outcome == "dead_letter" for record in job.telemetry.records)
    with sqlite3.connect(tmp_path / "observations.sqlite3") as connection:
        payload, attempts = connection.execute(
            "SELECT payload_json, attempts FROM pending_observations WHERE message_id = 'fails'"
        ).fetchone()
    assert payload == "{}"
    assert attempts == 1


async def test_durable_spool_drains_more_than_memory_capacity_without_restart(
    tmp_path: Path,
) -> None:
    service = RecoveredService(expected_calls=7)
    ready = asyncio.Event()
    job = RelationshipObservationJob(
        service, max_queue_size=1, spool_path=tmp_path / "observations.sqlite3"
    )
    for index in range(7):
        assert job.submit(envelope(str(index)))

    ready.set()
    job.start(ready.wait)
    await asyncio.wait_for(service.all_processed.wait(), timeout=1)
    await job.close()

    assert service.calls == [str(index) for index in range(7)]


async def test_spool_retries_until_dead_letter_without_restart(tmp_path: Path) -> None:
    service = Service()
    ready = asyncio.Event()
    ready.set()
    path = tmp_path / "observations.sqlite3"
    job = RelationshipObservationJob(
        service,
        max_queue_size=1,
        retry_limit=0,
        retry_backoff_seconds=0.01,
        recovery_attempt_limit=3,
        spool_path=path,
    )
    assert job.submit(envelope("fails"))
    job.start(ready.wait)
    await asyncio.wait_for(service.third_call.wait(), timeout=1)
    await job.close()

    assert len(service.calls) == 3
    assert any(record.outcome == "dead_letter" for record in job.telemetry.records)


def test_spool_file_is_private_and_expired_payload_is_purged(tmp_path: Path) -> None:
    path = tmp_path / "observations.sqlite3"
    spool = RelationshipObservationSpool(path, ttl_seconds=0.001)
    spool.put(ObservationInput.from_envelope(envelope("private")))
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    time.sleep(0.01)
    assert spool.pending(1) == ()
    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM pending_observations").fetchone()[0]
    assert count == 0


def test_legacy_spool_rows_without_expiry_are_purged_on_migration(tmp_path: Path) -> None:
    path = tmp_path / "legacy-observations.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE pending_observations (
                message_id TEXT PRIMARY KEY,
                payload_json TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                dead_letter INTEGER NOT NULL DEFAULT 0,
                last_failure TEXT
            )"""
        )
        connection.execute(
            "INSERT INTO pending_observations(message_id, payload_json) VALUES (?, ?)",
            ("legacy", '{"content": "sensitive legacy content"}'),
        )

    spool = RelationshipObservationSpool(path)

    assert spool.pending(1) == ()
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM pending_observations").fetchone()[0] == 0


async def test_live_traffic_cannot_starve_bounded_archive_batches() -> None:
    service = ArchiveService()
    ready = asyncio.Event()
    ready.set()
    job = RelationshipObservationJob(service, max_queue_size=2)
    job.start(ready.wait)
    for index in range(4):
        assert job.submit(envelope(f"live-{index}"))

    await asyncio.wait_for(service.archive_processed.wait(), timeout=1)
    await job.close()

    assert service.archive_batches >= 1
