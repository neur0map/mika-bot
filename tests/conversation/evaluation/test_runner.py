"""Blind conversation benchmark behavior contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.evaluation import (
    BenchmarkCase,
    BenchmarkTurn,
    HiddenExpectations,
    VisibleTurn,
    load_cases,
    run_cases,
)


async def test_runner_never_passes_hidden_expectations_to_responder() -> None:
    seen: list[ConversationEnvelope] = []

    async def responder(envelope: ConversationEnvelope) -> VisibleTurn:
        seen.append(envelope)
        return VisibleTurn(reply="yeah that's absolutely you")

    case = BenchmarkCase(
        case_id="joke-1",
        category="joke",
        turns=(BenchmarkTurn("u1", "carlos", "this is literally you"),),
        hidden_expectations=HiddenExpectations(
            participate=True,
            allowed_actions=("reply",),
            expected_intent="joke",
            forbidden_phrases=("as an assistant",),
        ),
    )

    report = await run_cases((case,), responder)

    assert len(seen) == 1
    assert "expected_intent" not in repr(seen[0])
    assert "benchmark" not in seen[0].text.lower()
    assert report.results[0].score == 1.0


async def test_scoring_reports_action_and_style_failures() -> None:
    async def responder(envelope: ConversationEnvelope) -> VisibleTurn:
        return VisibleTurn(
            reply="As an assistant, " + "x" * 80,
            actions=("reply", "gif"),
            used_tools=(),
        )

    case = BenchmarkCase(
        case_id="facts-1",
        category="current_facts",
        turns=(BenchmarkTurn("u1", "alice", "what happened today?"),),
        hidden_expectations=HiddenExpectations(
            participate=True,
            allowed_actions=("reply",),
            max_reply_chars=60,
            forbidden_phrases=("as an assistant",),
            expected_tool=True,
        ),
    )

    result = (await run_cases((case,), responder)).results[0]

    assert set(result.failures) == {
        "disallowed_action:gif",
        "forbidden_phrase:as an assistant",
        "missing_expected_tool",
        "reply_too_long",
    }
    assert result.score == 0.2


def test_fixture_contains_balanced_blind_cases() -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "conversation_benchmark_v1.json"
    cases = load_cases(fixture, created_at=datetime(2026, 8, 16, tzinfo=UTC))

    assert len(cases) >= 48
    assert len({case.category for case in cases}) >= 15
    assert all(case.turns for case in cases)
    assert all("benchmark" not in turn.text.lower() for case in cases for turn in case.turns)
