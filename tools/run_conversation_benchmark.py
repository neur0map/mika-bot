#!/usr/bin/env python3
"""Run or validate the versioned blind conversation benchmark."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from mika.ai.llm.client import LLMClient
from mika.conversation.actions import ActionPlanner, ExecutionResult
from mika.conversation.context import ContextSelector, TurnObserver
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.engine import ConversationEngine
from mika.conversation.evaluation import VisibleTurn, load_cases, run_cases
from mika.conversation.evaluation.adapter import (
    EvidenceRecordingGenerator,
    visible_from_action,
)
from mika.conversation.participation import ParticipationPlanner
from mika.conversation.tools import ToolPlanner

_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE = _ROOT / "tests" / "fixtures" / "conversation_benchmark_v1.json"
_MINIMUM_CASES = 48


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("staged",), default="staged")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


class _BenchmarkMemory:
    def __init__(self) -> None:
        self._rows: dict[str, list[tuple[str, str, str]]] = {}

    async def recent(self, channel_id: str) -> list[tuple[str, str, str]]:
        return self._rows.get(channel_id, [])

    async def remember(self, **values: str) -> None:
        self._rows.setdefault(values["channel_id"], []).append(
            (values["role"], values["author_name"], values["content"])
        )


class _DiscardTraces:
    async def add(self, trace: object) -> None:
        return None


async def _staged() -> dict[str, object]:
    cases = load_cases(_FIXTURE, created_at=datetime.now(UTC))
    memory = _BenchmarkMemory()
    client = LLMClient()
    generator = EvidenceRecordingGenerator(client)
    engine = ConversationEngine(
        ContextSelector(memory),
        ParticipationPlanner(),
        ToolPlanner(),
        generator,
        ActionPlanner(),
        TurnObserver(memory),
        _DiscardTraces(),
    )
    await client.startup()

    async def respond(envelope: ConversationEnvelope) -> VisibleTurn:
        action = await engine.handle(envelope)
        evidence = generator.take(envelope.message_id)
        await engine.observe(
            envelope,
            action,
            ExecutionResult(
                "benchmark-reply" if action.reply else None,
                action.reactions,
                "benchmark-media" if action.media else None,
                (),
            ),
        )
        return visible_from_action(action, evidence)

    try:
        report = await run_cases(cases, respond)
    finally:
        await client.shutdown()
    categories: dict[str, list[float]] = {}
    for result in report.results:
        categories.setdefault(result.category, []).append(result.score)
    return {
        "version": 1,
        "mode": "staged",
        "score": report.score,
        "case_count": len(report.results),
        "categories": {
            category: round(sum(scores) / len(scores), 4)
            for category, scores in sorted(categories.items())
        },
        "results": [asdict(result) for result in report.results],
    }


def _validate() -> dict[str, object]:
    cases = load_cases(_FIXTURE, created_at=datetime.now(UTC))
    leaked = [
        case.case_id
        for case in cases
        if any("benchmark" in turn.text.casefold() for turn in case.turns)
    ]
    return {
        "version": 1,
        "valid": not leaked and len(cases) >= _MINIMUM_CASES,
        "case_count": len(cases),
        "category_count": len({case.category for case in cases}),
        "prompt_leaks": leaked,
    }


def main() -> None:
    """Validate fixtures or execute the configured staged responder."""
    arguments = _arguments()
    payload = _validate() if arguments.dry_run else asyncio.run(_staged())
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)  # noqa: T201


if __name__ == "__main__":
    main()
