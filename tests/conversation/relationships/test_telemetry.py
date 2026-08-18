"""Content-free relationship operation telemetry."""

import asyncio
from time import monotonic

import pytest

from mika.conversation.relationships.telemetry import RelationshipTelemetry


class _CooperativeSink:
    cancellation_cooperative = True

    def __init__(self, write) -> None:
        self._write = write

    async def write(self, record: object) -> None:
        await self._write(record)


def test_telemetry_rejects_sink_without_cancellation_contract() -> None:
    async def arbitrary_callable(record: object) -> None:
        del record

    with pytest.raises(TypeError, match="cancellation-cooperative"):
        RelationshipTelemetry(sink=arbitrary_callable)


def test_telemetry_rejects_contract_marker_without_write_method() -> None:
    class InvalidSink:
        cancellation_cooperative = True

    with pytest.raises(TypeError, match="async write"):
        RelationshipTelemetry(sink=InvalidSink())


def test_telemetry_rejects_cooperative_sink_with_sync_write() -> None:
    class SyncSink:
        cancellation_cooperative = True

        def write(self, record: object) -> None:
            del record

    with pytest.raises(TypeError, match="async write"):
        RelationshipTelemetry(sink=SyncSink())


def test_telemetry_hashes_correlation_and_keeps_only_operational_fields() -> None:
    telemetry = RelationshipTelemetry()

    telemetry.emit(
        "observation",
        "failed",
        correlation_id="raw-message-id",
        duration_ms=12.5,
        candidate_count=2,
        selected_count=1,
        rejected_count=1,
        estimated_tokens=0,
        fallback_reason="RuntimeError",
        profile_changed=None,
        policy_version_id="policy-1",
        phase_durations_ms={"queue": 1.5, "extract": 11.0},
    )

    record = telemetry.records[0]
    assert record.correlation_hash.startswith("sha256:")
    assert "raw-message-id" not in repr(record)
    assert record.outcome == "failed"
    assert record.fallback_reason == "RuntimeError"
    assert record.phase_durations_ms == {"queue": 1.5, "extract": 11.0}


async def test_telemetry_persists_actual_operation_records() -> None:
    saved = []

    async def save(record: object) -> None:
        saved.append(record)

    telemetry = RelationshipTelemetry(sink=_CooperativeSink(save))
    telemetry.emit(
        "retrieval",
        "fallback",
        correlation_id="secret-query",
        duration_ms=8.0,
        candidate_count=3,
        selected_count=1,
        rejected_count=2,
        estimated_tokens=12,
        fallback_reason="semantic_unavailable",
        profile_changed=None,
        policy_version_id="policy-1",
    )
    await telemetry.flush()

    assert len(saved) == 1
    assert "secret-query" not in repr(saved)


async def test_telemetry_uses_one_worker_retries_and_flushes_deterministically() -> None:
    attempts = 0
    saved = []

    async def flaky_save(record: object) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary")
        saved.append(record)

    telemetry = RelationshipTelemetry(sink=_CooperativeSink(flaky_save))
    for correlation in ("one", "two"):
        telemetry.emit(
            "retrieval",
            "ok",
            correlation_id=correlation,
            duration_ms=1,
            candidate_count=0,
            selected_count=0,
            rejected_count=0,
            estimated_tokens=0,
            fallback_reason=None,
            profile_changed=None,
            policy_version_id="policy-1",
        )
    workers = {task for task in asyncio.all_tasks() if task.get_name() == "relationship-telemetry"}
    await telemetry.flush()

    assert len(workers) == 1
    assert len(saved) == 2
    assert attempts == 3
    assert telemetry.last_sink_failure is None
    await telemetry.close()


async def test_telemetry_close_bounds_a_wedged_sink_and_accounts_pending_work() -> None:
    wedged = asyncio.Event()

    async def never_returns(record: object) -> None:
        del record
        await wedged.wait()

    telemetry = RelationshipTelemetry(
        sink=_CooperativeSink(never_returns),
        sink_timeout_seconds=0.01,
        close_timeout_seconds=0.05,
    )
    for correlation in ("one", "two"):
        telemetry.emit(
            "retrieval",
            "ok",
            correlation_id=correlation,
            duration_ms=1,
            candidate_count=0,
            selected_count=0,
            rejected_count=0,
            estimated_tokens=0,
            fallback_reason=None,
            profile_changed=None,
            policy_version_id="policy-1",
        )

    started = monotonic()
    await telemetry.close()

    assert monotonic() - started < 0.5
    assert telemetry.last_sink_failure == "telemetry_flush_timeout"
    assert telemetry.dropped_sink_records >= 1
    assert telemetry.pending_sink_records == 0


async def test_telemetry_awaits_cooperative_sink_cleanup_when_write_times_out() -> None:
    cleanup_completed = asyncio.Event()

    async def slow_write(record: object) -> None:
        del record
        try:
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            cleanup_completed.set()

    telemetry = RelationshipTelemetry(
        sink=_CooperativeSink(slow_write),
        sink_timeout_seconds=0.01,
        close_timeout_seconds=0.05,
    )
    telemetry.emit(
        "retrieval",
        "ok",
        correlation_id="wedged",
        duration_ms=1,
        candidate_count=0,
        selected_count=0,
        rejected_count=0,
        estimated_tokens=0,
        fallback_reason=None,
        profile_changed=None,
        policy_version_id="policy-1",
    )

    started = monotonic()
    await telemetry.close()

    assert monotonic() - started < 0.5
    assert cleanup_completed.is_set()
    assert telemetry.pending_sink_records == 0
