"""Stateful, privacy-safe relationship-memory benchmark contracts."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mika.conversation.context.retrieval import MemoryRecall
from mika.conversation.evaluation.relationship_memory import (
    BenchmarkMode,
    RelationshipBenchmarkBackend,
    load_relationship_cases,
    run_local_relationship_benchmark,
    run_relationship_benchmark,
    write_case_artifacts,
)
from mika.conversation.evaluation.relationship_memory_backend import LocalBenchmarkBackend
from mika.conversation.relationships.contracts import RelationDecision
from mika.conversation.relationships.service import ObservationInput

FIXTURE = Path(__file__).parents[2] / "fixtures" / "relationship_memory_benchmark_v1.json"


class RecordingBackend(RelationshipBenchmarkBackend):
    """Record visible benchmark inputs and return deterministic claim selections."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []
        self.active: dict[str, tuple[str, str, str | None, str]] = {}

    async def observe(self, observation: ObservationInput) -> None:
        self.events.append(("observe", observation.message_id))
        text = observation.text.casefold()
        if "my name is" in text:
            self.active[observation.subject_user_id] = (
                observation.message_id,
                observation.visibility_kind,
                observation.guild_id,
                observation.channel_id,
            )

    async def recall(self, observation: ObservationInput) -> MemoryRecall:
        self.events.append(("recall", observation.message_id))
        selected = tuple(
            record[0]
            for subject, record in self.active.items()
            if subject == observation.subject_user_id
            and record[1] == observation.visibility_kind
            and record[2] == observation.guild_id
            and (record[1] != "direct_message" or record[3] == observation.channel_id)
        )
        return MemoryRecall(
            relationship_retrieval=True,
            candidate_ids=tuple(record[0] for record in self.active.values()),
            selected_ids=selected,
            selected_tiers={claim_id: "index" for claim_id in selected},
            latency_ms=0.5,
        )

    def classify(self, observation: ObservationInput) -> RelationDecision:
        relation = (
            "correction" if observation.text.casefold().startswith("actually") else "follow_up"
        )
        return RelationDecision(relation, 0.95, "fixture")

    async def source_ids_for_candidates(self, candidate_ids: tuple[str, ...]) -> tuple[str, ...]:
        return candidate_ids

    async def consolidate(self, observation: ObservationInput) -> None:
        self.events.append(("consolidate", observation.message_id))

    async def seed_inference(self, observation: ObservationInput) -> None:
        self.events.append(("seed_inference", observation.message_id))


def test_manifest_contains_required_held_out_behaviors() -> None:
    cases = load_relationship_cases(FIXTURE)

    tags = {tag for case in cases for tag in case.tags}
    assert {
        "correction",
        "contradiction",
        "private_isolation",
        "sensitive_abstention",
        "stale_inference",
        "behavioral_activation",
    } <= tags
    assert all(case.case_id and case.turns and case.supported_modes for case in cases)
    stale = next(case for case in cases if "stale_inference" in case.tags)
    assert sum(turn.action == "seed_inference" for turn in stale.turns) == 1
    assert sum(turn.action == "consolidate" for turn in stale.turns) == 2


@pytest.mark.asyncio
async def test_replay_is_chronological_and_hides_expectations_from_backend() -> None:
    backend = RecordingBackend()
    cases = load_relationship_cases(FIXTURE)[:1]

    report = await run_relationship_benchmark(cases, BenchmarkMode.LEXICAL, backend)

    assert backend.events == [
        ("observe", "identity-correction-0"),
        ("observe", "identity-correction-1"),
        ("recall", "identity-correction-2"),
    ]
    assert report.results[0].case_id == "identity-correction"
    assert report.results[0].expected_claim_labels == ()


@pytest.mark.asyncio
async def test_aggregate_gates_and_artifacts_are_content_free(tmp_path: Path) -> None:
    backend = RecordingBackend()
    cases = load_relationship_cases(FIXTURE)
    report = await run_relationship_benchmark(cases, BenchmarkMode.LEXICAL, backend)
    artifact = tmp_path / "cases.jsonl"

    write_case_artifacts(report, artifact)

    records = [json.loads(line) for line in artifact.read_text(encoding="utf-8").splitlines()]
    assert records
    allowed = {
        "case_id",
        "mode",
        "relation_class",
        "privacy_class",
        "selected_ids",
        "rejected_ids",
        "candidate_count",
        "selected_count",
        "latency_ms",
        "local_component_latency_ms",
        "metrics",
        "passed",
    }
    assert all(set(record) == allowed for record in records)
    serialized = artifact.read_text(encoding="utf-8")
    assert "my name is" not in serialized.casefold()
    assert "privatealias" not in serialized.casefold()
    assert report.metrics.cross_scope_leakage == 0
    assert report.metrics.p95_local_latency_ms < 100


def test_fixture_timestamps_are_deterministic() -> None:
    cases = load_relationship_cases(FIXTURE)

    assert cases[0].turns[0].created_at == datetime(2026, 8, 1, 12, tzinfo=UTC)


def test_cli_writes_aggregate_and_safe_case_artifacts(tmp_path: Path) -> None:
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [
            sys.executable,
            "tools/run_relationship_memory_benchmark.py",
            "--fixture",
            str(FIXTURE),
            "--mode",
            "lexical",
            "--output-dir",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    aggregate = json.loads(completed.stdout)
    assert aggregate["passed"] is True
    assert aggregate["metrics"]["cross_scope_leakage"] == 0
    assert (tmp_path / "relationship-memory-lexical.json").exists()
    artifact = tmp_path / "relationship-memory-lexical-cases.jsonl"
    assert artifact.exists()
    assert "privatealias" not in artifact.read_text(encoding="utf-8").casefold()


@pytest.mark.asyncio
async def test_real_local_store_passes_rollout_gates(tmp_path: Path) -> None:
    cases = load_relationship_cases(FIXTURE)

    report = await run_local_relationship_benchmark(
        cases,
        BenchmarkMode.LEXICAL,
        database_path=tmp_path / "benchmark.db",
    )

    assert report.metrics.passed
    assert report.metrics.recall_quality == 1.0
    assert report.metrics.cross_scope_leakage == 0
    assert report.metrics.correction_adoption == 1.0
    assert report.metrics.correct_person_attribution == 1.0
    assert report.metrics.p95_local_latency_ms < 100


@pytest.mark.asyncio
async def test_configured_honcho_mode_calls_external_recall_without_artifact_content(
    tmp_path: Path,
) -> None:
    queries: list[str] = []

    async def honcho_recall(query: str) -> str:
        queries.append(query)
        return "external-private-context"

    report = await run_local_relationship_benchmark(
        load_relationship_cases(FIXTURE),
        BenchmarkMode.LOCAL_PLUS_HONCHO,
        database_path=tmp_path / "honcho.db",
        external_recall=honcho_recall,
    )
    artifact = tmp_path / "honcho.jsonl"
    write_case_artifacts(report, artifact)

    assert queries
    assert not report.metrics.passed
    assert not report.metrics.rollout_eligible
    assert report.metrics.cross_scope_leakage is None
    assert "external-private-context" not in artifact.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_empty_retriever_cannot_pass_absolute_or_attribution_gates() -> None:
    backend = RecordingBackend()
    backend.active.clear()
    case = load_relationship_cases(FIXTURE)[0]
    case = type(case)(
        case.case_id,
        case.relation_class,
        case.privacy_class,
        case.tags,
        case.supported_modes,
        (case.turns[-1],),
        case.hidden,
    )

    report = await run_relationship_benchmark((case,), BenchmarkMode.LEXICAL, backend)

    assert not report.metrics.passed
    assert report.metrics.recall_quality == 0.0
    assert report.metrics.correct_person_attribution == 0.0
    assert not report.metrics.no_recall_regression


@pytest.mark.asyncio
async def test_p95_uses_measured_wall_clock_not_reported_component_latency() -> None:
    class SlowBackend(RecordingBackend):
        async def recall(self, observation: ObservationInput) -> MemoryRecall:
            await asyncio.sleep(0.11)
            return MemoryRecall(latency_ms=0.01, relationship_retrieval=True)

    case = load_relationship_cases(FIXTURE)[2]
    report = await run_relationship_benchmark((case,), BenchmarkMode.LEXICAL, SlowBackend())

    assert report.results[0].local_component_latency_ms == 0.01
    assert report.metrics.p95_local_latency_ms >= 100
    assert not report.metrics.passed


@pytest.mark.asyncio
async def test_stale_candidate_inference_expires_through_real_consolidation(
    tmp_path: Path,
) -> None:
    backend = await LocalBenchmarkBackend.create(tmp_path / "lifecycle.db", "lexical")
    stale = next(
        case for case in load_relationship_cases(FIXTURE) if "stale_inference" in case.tags
    )
    try:
        await run_relationship_benchmark((stale,), BenchmarkMode.LEXICAL, backend)
    finally:
        await backend.close()

    assert backend.lifecycle_snapshots[0]["candidate"] == 1
    assert backend.lifecycle_snapshots[1]["expired"] == 1


@pytest.mark.asyncio
async def test_repeated_behavior_fixture_activates_after_real_threshold(tmp_path: Path) -> None:
    backend = await LocalBenchmarkBackend.create(tmp_path / "behavior.db", "lexical")
    case = next(
        case for case in load_relationship_cases(FIXTURE) if "behavioral_activation" in case.tags
    )
    try:
        report = await run_relationship_benchmark((case,), BenchmarkMode.LEXICAL, backend)
    finally:
        await backend.close()

    assert backend.lifecycle_snapshots[0]["active"] == 1
    assert report.results[0].metrics["recall_hit"] is True
