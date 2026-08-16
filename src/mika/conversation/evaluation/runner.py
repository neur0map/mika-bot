"""Blind benchmark runner that exposes only ordinary conversation envelopes."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from mika.conversation.contracts import ConversationEnvelope, ReferencedMessage
from mika.conversation.evaluation.cases import BenchmarkCase, BenchmarkTurn, VisibleTurn
from mika.conversation.evaluation.scoring import score_turn

Responder = Callable[[ConversationEnvelope], Awaitable[VisibleTurn]]


@dataclass(frozen=True, slots=True)
class CaseResult:
    """One visible result and its post-generation deterministic score."""

    case_id: str
    category: str
    visible_turn: VisibleTurn
    latency_ms: float
    score: float
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """Aggregate results for a benchmark run."""

    results: tuple[CaseResult, ...]

    @property
    def score(self) -> float:
        """Return mean deterministic score across cases."""
        if not self.results:
            return 0.0
        return round(sum(result.score for result in self.results) / len(self.results), 4)


def _reference(case: BenchmarkCase, turn: BenchmarkTurn) -> ReferencedMessage | None:
    if turn.reply_to is None or not 0 <= turn.reply_to < len(case.turns):
        return None
    target = case.turns[turn.reply_to]
    return ReferencedMessage(
        message_id=f"{case.case_id}-{turn.reply_to}",
        author_id=target.author_id,
        author_name=target.author_name,
        text=target.text,
        media=target.media,
    )


def _envelope(case: BenchmarkCase) -> ConversationEnvelope:
    turn = case.turns[-1]
    position = len(case.turns) - 1
    return ConversationEnvelope(
        message_id=f"{case.case_id}-{position}",
        channel_id=f"evaluation-{case.case_id}",
        guild_id="evaluation",
        author_id=turn.author_id,
        author_name=turn.author_name,
        text=turn.text,
        mentioned=turn.mentioned,
        created_at=case.created_at or datetime(2026, 1, 1, tzinfo=UTC),
        media=turn.media,
        referenced=_reference(case, turn),
    )


async def run_cases(cases: Sequence[BenchmarkCase], responder: Responder) -> BenchmarkReport:
    """Run cases without exposing scoring expectations to the responder."""
    results: list[CaseResult] = []
    for case in cases:
        envelope = _envelope(case)
        started = time.perf_counter()
        visible = await responder(envelope)
        latency_ms = (time.perf_counter() - started) * 1000
        score, failures = score_turn(visible, case.hidden_expectations)
        results.append(
            CaseResult(
                case_id=case.case_id,
                category=case.category,
                visible_turn=visible,
                latency_ms=latency_ms,
                score=score,
                failures=failures,
            )
        )
    return BenchmarkReport(tuple(results))
