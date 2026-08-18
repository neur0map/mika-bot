"""Content-free relationship operation telemetry."""

import asyncio
from time import monotonic

from mika.conversation.relationships.telemetry import RelationshipTelemetry


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

    telemetry = RelationshipTelemetry(sink=save)
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

    telemetry = RelationshipTelemetry(sink=flaky_save)
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
        sink=never_returns,
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
