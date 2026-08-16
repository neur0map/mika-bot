"""Privacy-safe trace aggregates and benchmark summaries for operators."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from mika.core.config import get_settings
from mika.persistence.conversations.traces import TurnTraceRepository
from mika.persistence.engine import session

_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = _ROOT / "tests" / "fixtures" / "conversation_benchmark_v1.json"


def summarize_traces(traces: Iterable[Any]) -> dict[str, Any]:
    """Aggregate stage outcomes without returning trace or Discord identifiers."""
    stage_counts: dict[str, Counter[str]] = defaultdict(Counter)
    turn_count = 0
    for trace in traces:
        turn_count += 1
        for stage in trace.stages:
            stage_counts[str(stage.stage)][str(stage.outcome)] += 1
    return {
        "turn_count": turn_count,
        "stages": {
            stage: dict(sorted(outcomes.items()))
            for stage, outcomes in sorted(stage_counts.items())
        },
    }


def sanitize_benchmark(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Keep aggregate benchmark fields and drop all case-level generated output."""
    categories = payload.get("categories")
    safe_categories = categories if isinstance(categories, dict) else {}
    return {
        "version": payload.get("version"),
        "mode": payload.get("mode", "staged"),
        "score": payload.get("score"),
        "case_count": payload.get("case_count", 0),
        "categories": safe_categories,
    }


async def diagnostics_snapshot() -> dict[str, Any]:
    """Read recent diagnostics; failures degrade to an empty operator view."""
    try:
        async with session() as active:
            traces = await TurnTraceRepository(active).recent(100)
        trace_summary = summarize_traces(traces)
    except Exception:
        trace_summary = summarize_traces(())
    return {"traces": trace_summary, "benchmark": _benchmark_summary()}


def _benchmark_summary() -> dict[str, Any]:
    report = get_settings().data_dir / "conversation-benchmark.json"
    try:
        payload = json.loads(report.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return sanitize_benchmark(payload)
    except (OSError, json.JSONDecodeError):
        pass
    try:
        fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        case_count = len(fixture.get("cases", ())) if isinstance(fixture, dict) else 0
    except (OSError, json.JSONDecodeError):
        case_count = 0
    return sanitize_benchmark(
        {"version": 1, "mode": "staged", "score": None, "case_count": case_count}
    )
