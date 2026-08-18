"""Content-free relationship operation telemetry."""

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
