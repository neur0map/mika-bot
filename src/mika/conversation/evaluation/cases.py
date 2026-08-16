"""Contracts and fixture loading for blind conversation benchmarks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from mika.conversation.contracts import MediaAsset


@dataclass(frozen=True, slots=True)
class BenchmarkTurn:
    """One visible Discord-like message in a benchmark conversation."""

    author_id: str
    author_name: str
    text: str
    mentioned: bool = False
    media: tuple[MediaAsset, ...] = ()
    reply_to: int | None = None


@dataclass(frozen=True, slots=True)
class HiddenExpectations:
    """Post-generation rubric that is never passed to a responder."""

    participate: bool
    allowed_actions: tuple[str, ...]
    expected_intent: str = ""
    max_reply_chars: int = 180
    forbidden_phrases: tuple[str, ...] = ()
    expected_tool: bool | None = None
    expected_media_context: bool | None = None


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """Visible conversation turns paired with a hidden scoring rubric."""

    case_id: str
    category: str
    turns: tuple[BenchmarkTurn, ...]
    hidden_expectations: HiddenExpectations
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class VisibleTurn:
    """Observable output returned by a benchmark responder."""

    reply: str = ""
    actions: tuple[str, ...] = ()
    used_tools: tuple[str, ...] = ()
    used_media_context: bool = False

    @property
    def normalized_actions(self) -> tuple[str, ...]:
        """Include reply as an action when visible text is present."""
        actions = self.actions
        if self.reply and "reply" not in actions:
            actions = ("reply", *actions)
        return actions


def _media(raw: dict[str, Any]) -> MediaAsset:
    return MediaAsset(
        kind=raw.get("kind", "unknown"),
        url=str(raw["url"]),
        filename=str(raw.get("filename", "")),
        content_type=str(raw.get("content_type", "")),
        source=str(raw.get("source", "fixture")),
    )


def load_cases(path: Path, *, created_at: datetime) -> tuple[BenchmarkCase, ...]:
    """Load benchmark cases from a versioned JSON fixture."""
    document = json.loads(path.read_text(encoding="utf-8"))
    cases: list[BenchmarkCase] = []
    for raw_case in document["cases"]:
        turns = tuple(
            BenchmarkTurn(
                author_id=str(turn["author_id"]),
                author_name=str(turn["author_name"]),
                text=str(turn["text"]),
                mentioned=bool(turn.get("mentioned", False)),
                media=tuple(_media(asset) for asset in turn.get("media", ())),
                reply_to=turn.get("reply_to"),
            )
            for turn in raw_case["turns"]
        )
        hidden = raw_case["hidden_expectations"]
        cases.append(
            BenchmarkCase(
                case_id=str(raw_case["case_id"]),
                category=str(raw_case["category"]),
                turns=turns,
                hidden_expectations=HiddenExpectations(
                    participate=bool(hidden["participate"]),
                    allowed_actions=tuple(hidden["allowed_actions"]),
                    expected_intent=str(hidden.get("expected_intent", "")),
                    max_reply_chars=int(hidden.get("max_reply_chars", 180)),
                    forbidden_phrases=tuple(hidden.get("forbidden_phrases", ())),
                    expected_tool=hidden.get("expected_tool"),
                    expected_media_context=hidden.get("expected_media_context"),
                ),
                created_at=created_at,
            )
        )
    return tuple(cases)
