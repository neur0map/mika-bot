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
