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
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.evaluation import VisibleTurn, load_cases, run_cases

_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE = _ROOT / "tests" / "fixtures" / "conversation_benchmark_v1.json"
_MINIMUM_CASES = 48


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("legacy",), default="legacy")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _media_context(envelope: ConversationEnvelope) -> str:
    if not envelope.visual_inputs:
        return ""
    kinds = ", ".join(asset.kind for asset in envelope.visual_inputs)
    reference = f" Reply target: {envelope.referenced.author_name}." if envelope.referenced else ""
    return f"Attached visual media: {kinds}.{reference}"


async def _legacy() -> dict[str, object]:
    cases = load_cases(_FIXTURE, created_at=datetime.now(UTC))
    client = LLMClient()
    await client.startup()

    async def respond(envelope: ConversationEnvelope) -> VisibleTurn:
        turn = await client.reply(
            channel_id=envelope.channel_id,
            author_id=envelope.author_id,
            author_name=envelope.author_name,
            text=envelope.text,
            media_context=_media_context(envelope),
            media_urls=[asset.url for asset in envelope.visual_inputs],
        )
        actions: list[str] = []
        if turn.reactions:
            actions.append("reaction")
        if turn.media.kind != "none":
            actions.append(turn.media.kind)
        return VisibleTurn(reply=turn.reply, actions=tuple(actions))

    try:
        report = await run_cases(cases, respond)
    finally:
        await client.shutdown()
    categories: dict[str, list[float]] = {}
    for result in report.results:
        categories.setdefault(result.category, []).append(result.score)
    return {
        "version": 1,
        "mode": "legacy",
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
    """Validate fixtures or execute the configured legacy responder."""
    arguments = _arguments()
    payload = _validate() if arguments.dry_run else asyncio.run(_legacy())
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)  # noqa: T201


if __name__ == "__main__":
    main()
