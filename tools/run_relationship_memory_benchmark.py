#!/usr/bin/env python3
"""Run the versioned stateful relationship-memory benchmark."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path

from mika.ai.llm.memory.honcho import HonchoMemory
from mika.conversation.evaluation.relationship_memory import (
    BenchmarkMode,
    load_relationship_cases,
    report_values,
    run_local_relationship_benchmark,
    write_case_artifacts,
)
from mika.core.config import get_settings

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_FIXTURE = _ROOT / "tests/fixtures/relationship_memory_benchmark_v1.json"
_DEFAULT_OUTPUT = _ROOT / "var/benchmarks"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=_DEFAULT_FIXTURE)
    parser.add_argument("--output-dir", type=Path, default=_DEFAULT_OUTPUT)
    parser.add_argument(
        "--mode",
        choices=("lexical", "local_hybrid", "local_plus_honcho", "all"),
        default="all",
    )
    return parser.parse_args()


def _modes(requested: str) -> tuple[BenchmarkMode, ...]:
    if requested != "all":
        mode = BenchmarkMode(requested)
        if mode is BenchmarkMode.LOCAL_PLUS_HONCHO and not get_settings().memory.honcho_enabled:
            raise ValueError("local_plus_honcho requires configured Honcho memory")
        return (mode,)
    modes = [BenchmarkMode.LEXICAL, BenchmarkMode.LOCAL_HYBRID]
    if get_settings().memory.honcho_enabled:
        modes.append(BenchmarkMode.LOCAL_PLUS_HONCHO)
    return tuple(modes)


async def _run(arguments: argparse.Namespace) -> list[dict[str, object]]:
    cases = load_relationship_cases(arguments.fixture)
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    baseline: float | None = None
    honcho_recall = _honcho_recall()
    for mode in _modes(arguments.mode):
        with tempfile.TemporaryDirectory(prefix=f"relationship-{mode.value}-") as directory:
            report = await run_local_relationship_benchmark(
                cases,
                mode,
                database_path=Path(directory) / "memory.db",
                baseline_recall_quality=baseline,
                external_recall=(
                    honcho_recall if mode is BenchmarkMode.LOCAL_PLUS_HONCHO else None
                ),
            )
        if mode is BenchmarkMode.LEXICAL:
            baseline = report.metrics.recall_quality
        aggregate = report_values(report)
        aggregate_path = arguments.output_dir / f"relationship-memory-{mode.value}.json"
        aggregate_path.write_text(
            json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        write_case_artifacts(
            report,
            arguments.output_dir / f"relationship-memory-{mode.value}-cases.jsonl",
        )
        reports.append(aggregate)
    return reports


def _honcho_recall() -> Callable[[str], Awaitable[str]] | None:
    if not get_settings().memory.honcho_enabled:
        return None
    return HonchoMemory().recall


def main() -> int:
    """Run requested modes and return nonzero when a rollout gate fails."""
    arguments = _arguments()
    try:
        reports = asyncio.run(_run(arguments))
    except ValueError as error:
        sys.stdout.write(json.dumps({"error": str(error)}, sort_keys=True) + "\n")
        return 2
    payload: object = reports[0] if len(reports) == 1 else reports
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    return 0 if all(bool(report["passed"]) for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
