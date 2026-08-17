"""Stateful held-out evaluation for evidence-backed relationship memory."""

from __future__ import annotations

import json
import math
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from time import perf_counter
from typing import Protocol, cast

from mika.conversation.context.retrieval import MemoryRecall
from mika.conversation.evaluation.relationship_memory_backend import LocalBenchmarkBackend
from mika.conversation.relationships.contracts import RelationDecision, RelationKind
from mika.conversation.relationships.service import ObservationInput

_CORRECTION_GATE = 0.95
_ATTRIBUTION_GATE = 0.98
_LOCAL_P95_GATE_MS = 100.0


class BenchmarkMode(StrEnum):
    """Supported relationship-retrieval configurations."""

    LEXICAL = "lexical"
    LOCAL_HYBRID = "local_hybrid"
    LOCAL_PLUS_HONCHO = "local_plus_honcho"


class RelationshipBenchmarkBackend(Protocol):
    """Visible-only observation and recall boundary used during replay."""

    async def observe(self, observation: ObservationInput) -> None: ...

    async def recall(self, observation: ObservationInput) -> MemoryRecall: ...

    def classify(self, observation: ObservationInput) -> RelationDecision: ...

    async def source_ids_for_candidates(self, candidate_ids: Sequence[str]) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class RelationshipBenchmarkTurn:
    """One chronological visible operation in a held-out case."""

    action: str
    author_id: str
    text: str
    visibility_kind: str
    guild_id: str | None
    channel_id: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RelationshipHiddenExpectations:
    """Post-replay rubric kept outside the backend boundary."""

    expected_source_turn_ids: tuple[str, ...]
    forbidden_source_turn_ids: tuple[str, ...]
    expected_relation: RelationKind
    correction_adopted: bool = False


@dataclass(frozen=True, slots=True)
class RelationshipBenchmarkCase:
    """Visible turns paired with a hidden relationship-memory rubric."""

    case_id: str
    relation_class: str
    privacy_class: str
    tags: tuple[str, ...]
    supported_modes: tuple[BenchmarkMode, ...]
    turns: tuple[RelationshipBenchmarkTurn, ...]
    hidden: RelationshipHiddenExpectations


@dataclass(frozen=True, slots=True)
class RelationshipCaseResult:
    """Content-free outcome for one stateful replay."""

    case_id: str
    mode: BenchmarkMode
    relation_class: str
    privacy_class: str
    selected_ids: tuple[str, ...]
    rejected_ids: tuple[str, ...]
    candidate_count: int
    selected_count: int
    latency_ms: float
    metrics: Mapping[str, float | int | bool]
    passed: bool
    expected_claim_labels: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RelationshipBenchmarkMetrics:
    """Aggregate rollout gates for one retrieval mode."""

    recall_quality: float
    cross_scope_leakage: int
    correction_adoption: float
    correct_person_attribution: float
    relation_accuracy: float
    irrelevant_rejection: float
    p95_local_latency_ms: float
    mean_prompt_tokens: float
    no_recall_regression: bool

    @property
    def passed(self) -> bool:
        """Return whether every mandatory rollout threshold passes."""
        return (
            self.no_recall_regression
            and self.cross_scope_leakage == 0
            and self.correction_adoption >= _CORRECTION_GATE
            and self.correct_person_attribution >= _ATTRIBUTION_GATE
            and self.p95_local_latency_ms < _LOCAL_P95_GATE_MS
        )


@dataclass(frozen=True, slots=True)
class RelationshipBenchmarkReport:
    """Per-case and aggregate results for one retrieval mode."""

    mode: BenchmarkMode
    results: tuple[RelationshipCaseResult, ...]
    metrics: RelationshipBenchmarkMetrics


def load_relationship_cases(path: Path) -> tuple[RelationshipBenchmarkCase, ...]:
    """Load a versioned relationship benchmark manifest."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("version") != 1:
        raise ValueError("unsupported relationship benchmark version")
    return tuple(_case(raw) for raw in document["cases"])


async def run_relationship_benchmark(
    cases: Sequence[RelationshipBenchmarkCase],
    mode: BenchmarkMode,
    backend: RelationshipBenchmarkBackend,
    *,
    baseline_recall_quality: float | None = None,
) -> RelationshipBenchmarkReport:
    """Replay visible turns chronologically, then score hidden expectations."""
    results: list[RelationshipCaseResult] = []
    token_costs: list[int] = []
    for case in cases:
        if mode not in case.supported_modes:
            continue
        recall = MemoryRecall(relationship_retrieval=True)
        relation: RelationKind = "follow_up"
        for position, turn in enumerate(case.turns):
            observation = _observation(case.case_id, position, turn)
            if turn.action == "observe":
                await backend.observe(observation)
                continue
            started = perf_counter()
            recall = await backend.recall(observation)
            measured_ms = (perf_counter() - started) * 1000
            relation = backend.classify(observation).relation
            recall = _with_measured_latency(recall, measured_ms)
        token_costs.append(recall.estimated_token_cost)
        source_ids = await backend.source_ids_for_candidates(recall.selected_ids)
        results.append(_score_case(case, mode, recall, relation, source_ids))
    metrics = _aggregate(results, token_costs, baseline_recall_quality)
    return RelationshipBenchmarkReport(mode, tuple(results), metrics)


def write_case_artifacts(report: RelationshipBenchmarkReport, path: Path) -> None:
    """Write content-free, one-record-per-case JSONL artifacts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(_artifact(result), sort_keys=True) for result in report.results]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


async def run_local_relationship_benchmark(
    cases: Sequence[RelationshipBenchmarkCase],
    mode: BenchmarkMode,
    *,
    database_path: Path,
    baseline_recall_quality: float | None = None,
    external_recall: Callable[[str], Awaitable[str]] | None = None,
) -> RelationshipBenchmarkReport:
    """Run production local relationship components against an isolated SQLite store."""
    backend = await LocalBenchmarkBackend.create(
        database_path, mode.value, external_recall=external_recall
    )
    try:
        return await run_relationship_benchmark(
            cases,
            mode,
            backend,
            baseline_recall_quality=baseline_recall_quality,
        )
    finally:
        await backend.close()


def report_values(report: RelationshipBenchmarkReport) -> dict[str, object]:
    """Return stable aggregate JSON suitable for CLI output."""
    metrics = report.metrics
    return {
        "version": 1,
        "mode": report.mode.value,
        "case_count": len(report.results),
        "passed": metrics.passed,
        "metrics": {
            "recall_quality": metrics.recall_quality,
            "cross_scope_leakage": metrics.cross_scope_leakage,
            "correction_adoption": metrics.correction_adoption,
            "correct_person_attribution": metrics.correct_person_attribution,
            "relation_accuracy": metrics.relation_accuracy,
            "irrelevant_rejection": metrics.irrelevant_rejection,
            "p95_local_latency_ms": metrics.p95_local_latency_ms,
            "mean_prompt_tokens": metrics.mean_prompt_tokens,
            "no_recall_regression": metrics.no_recall_regression,
        },
    }


def _case(raw: Mapping[str, object]) -> RelationshipBenchmarkCase:
    turns = tuple(_turn(item) for item in cast(list[Mapping[str, object]], raw["turns"]))
    hidden = cast(Mapping[str, object], raw["hidden_expectations"])
    return RelationshipBenchmarkCase(
        case_id=str(raw["case_id"]),
        relation_class=str(raw["relation_class"]),
        privacy_class=str(raw["privacy_class"]),
        tags=tuple(str(item) for item in cast(list[object], raw["tags"])),
        supported_modes=tuple(
            BenchmarkMode(str(item)) for item in cast(list[object], raw["supported_modes"])
        ),
        turns=turns,
        hidden=RelationshipHiddenExpectations(
            tuple(str(item) for item in cast(list[object], hidden["expected_source_turn_ids"])),
            tuple(str(item) for item in cast(list[object], hidden["forbidden_source_turn_ids"])),
            cast(RelationKind, str(hidden["expected_relation"])),
            bool(hidden.get("correction_adopted", False)),
        ),
    )


def _turn(raw: Mapping[str, object]) -> RelationshipBenchmarkTurn:
    created_at = datetime.fromisoformat(str(raw["created_at"]).replace("Z", "+00:00"))
    return RelationshipBenchmarkTurn(
        str(raw["action"]),
        str(raw["author_id"]),
        str(raw["text"]),
        str(raw["visibility_kind"]),
        None if raw.get("guild_id") is None else str(raw["guild_id"]),
        str(raw["channel_id"]),
        created_at,
    )


def _observation(case_id: str, position: int, turn: RelationshipBenchmarkTurn) -> ObservationInput:
    message_id = f"{case_id}-{position}"
    return ObservationInput(
        source_kind="relationship_benchmark",
        source_id=message_id,
        message_id=message_id,
        subject_user_id=turn.author_id,
        text=turn.text,
        created_at=turn.created_at,
        visibility_kind=turn.visibility_kind,
        guild_id=turn.guild_id,
        channel_id=turn.channel_id,
    )


def _with_measured_latency(recall: MemoryRecall, measured_ms: float) -> MemoryRecall:
    return replace(recall, latency_ms=recall.latency_ms or measured_ms)


def _score_case(
    case: RelationshipBenchmarkCase,
    mode: BenchmarkMode,
    recall: MemoryRecall,
    relation: RelationKind,
    selected_source_ids: Sequence[str],
) -> RelationshipCaseResult:
    selected = set(selected_source_ids)
    expected = set(case.hidden.expected_source_turn_ids)
    forbidden = set(case.hidden.forbidden_source_turn_ids)
    recall_hit = expected <= selected
    leakage = len(selected & forbidden)
    attribution = not selected or selected <= expected
    irrelevant_rejected = bool(expected) or not selected
    correction = not case.hidden.correction_adopted or (recall_hit and leakage == 0)
    relation_correct = relation == case.hidden.expected_relation
    metrics: dict[str, float | int | bool] = {
        "recall_hit": recall_hit,
        "recall_expected": bool(expected),
        "leakage_count": leakage,
        "attribution_correct": attribution,
        "correction_adopted": correction,
        "relation_correct": relation_correct,
        "irrelevant_rejected": irrelevant_rejected,
    }
    return RelationshipCaseResult(
        case.case_id,
        mode,
        case.relation_class,
        case.privacy_class,
        recall.selected_ids,
        recall.rejected_ids,
        len(recall.candidate_ids),
        len(recall.selected_ids),
        round(recall.latency_ms, 4),
        metrics,
        all(bool(value) for key, value in metrics.items() if key != "leakage_count")
        and leakage == 0,
    )


def _aggregate(
    results: Sequence[RelationshipCaseResult],
    token_costs: Sequence[int],
    baseline: float | None,
) -> RelationshipBenchmarkMetrics:
    total = len(results)
    if total == 0:
        return RelationshipBenchmarkMetrics(0, 0, 0, 0, 0, 0, 0, 0, False)
    correction_results = [item for item in results if item.relation_class == "correction"]
    expected_cases = [item for item in results if bool(item.metrics["recall_expected"])]
    recall_results = [item for item in expected_cases if bool(item.metrics["recall_hit"])]
    recall_quality = len(recall_results) / max(1, len(expected_cases))
    correction_adoption = _rate(correction_results, "correction_adopted", empty=1.0)
    attribution = _rate(results, "attribution_correct")
    relation_accuracy = _rate(results, "relation_correct")
    irrelevant = _rate(results, "irrelevant_rejected")
    latency = _percentile([item.latency_ms for item in results], 0.95)
    return RelationshipBenchmarkMetrics(
        round(recall_quality, 4),
        sum(int(item.metrics["leakage_count"]) for item in results),
        round(correction_adoption, 4),
        round(attribution, 4),
        round(relation_accuracy, 4),
        round(irrelevant, 4),
        round(latency, 4),
        round(sum(token_costs) / total, 4),
        baseline is None or recall_quality >= baseline,
    )


def _rate(results: Sequence[RelationshipCaseResult], key: str, *, empty: float = 0.0) -> float:
    if not results:
        return empty
    return sum(bool(item.metrics[key]) for item in results) / len(results)


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def _artifact(result: RelationshipCaseResult) -> dict[str, object]:
    return {
        "case_id": result.case_id,
        "mode": result.mode.value,
        "relation_class": result.relation_class,
        "privacy_class": result.privacy_class,
        "selected_ids": result.selected_ids,
        "rejected_ids": result.rejected_ids,
        "candidate_count": result.candidate_count,
        "selected_count": result.selected_count,
        "latency_ms": result.latency_ms,
        "metrics": dict(result.metrics),
        "passed": result.passed,
    }
