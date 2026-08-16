"""Conversation trace collection and privacy behavior."""

from __future__ import annotations

from mika.conversation.trace_service import TurnTraceService


def test_trace_service_records_ordered_safe_stages() -> None:
    trace = TurnTraceService("trace-1", "message-1", "channel-1")

    trace.record("ingress", "ready", details={"media_count": 1})
    trace.record("generation", "failed", reason="provider_error", duration_ms=12.5)

    assert [stage.stage for stage in trace.trace.stages] == ["ingress", "generation"]
    assert trace.trace.stages[1].reason == "provider_error"
    assert trace.trace.stages[1].duration_ms == 12.5


def test_trace_service_rejects_raw_text_and_provider_content() -> None:
    trace = TurnTraceService("trace-1", "message-1", "channel-1")

    trace.record(
        "generation",
        "ready",
        details={"raw_text": "private user text", "provider_output": "private output"},
    )

    assert trace.trace.stages[0].details == {"provider_output_present": True}
