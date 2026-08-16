"""Privacy-safe dashboard conversation diagnostics."""

from __future__ import annotations

from types import SimpleNamespace

from mika.web.conversation_diagnostics import sanitize_benchmark, summarize_traces


def test_trace_summary_exposes_aggregate_stages_without_identifiers() -> None:
    traces = [
        SimpleNamespace(
            message_id="secret-message",
            channel_id="secret-channel",
            stages=[
                SimpleNamespace(stage="participation", outcome="reply"),
                SimpleNamespace(stage="execution", outcome="visible"),
            ],
        ),
        SimpleNamespace(
            message_id="other",
            channel_id="other",
            stages=[SimpleNamespace(stage="participation", outcome="observe")],
        ),
    ]

    summary = summarize_traces(traces)

    assert summary == {
        "turn_count": 2,
        "stages": {
            "execution": {"visible": 1},
            "participation": {"observe": 1, "reply": 1},
        },
    }
    assert "secret" not in repr(summary)


def test_benchmark_summary_drops_case_level_outputs() -> None:
    summary = sanitize_benchmark(
        {
            "version": 1,
            "mode": "staged",
            "score": 0.82,
            "case_count": 48,
            "categories": {"joke": 0.9},
            "results": [{"reply": "private generated text"}],
        }
    )

    assert summary == {
        "version": 1,
        "mode": "staged",
        "score": 0.82,
        "case_count": 48,
        "categories": {"joke": 0.9},
    }
    assert "private generated text" not in repr(summary)
