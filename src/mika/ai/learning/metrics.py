"""Privacy-safe aggregate metrics for archived Mika turn decisions."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPLY_LENGTH_120 = 120
_REPLY_LENGTH_180 = 180
_REPLY_LENGTH_200 = 200


@dataclass(frozen=True, slots=True)
class TurnMetrics:
    """Aggregate quality signals that intentionally exclude conversation content."""

    turn_count: int
    parse_statuses: dict[str, int]
    reply_over_120: int
    reply_over_180: int
    reply_over_200: int
    reaction_turns: int
    selected_media_turns: int
    sent_media_turns: int
    inbound_media_turns: int
    inbound_media_action_turns: int
    silence_turns: int


def summarize_turn_payloads(payloads: Iterable[Mapping[str, Any]]) -> TurnMetrics:
    """Summarize turn telemetry without retaining message or author content."""
    rows = list(payloads)
    parse_statuses = Counter(str(row.get("parseStatus") or "unknown") for row in rows)
    reply_lengths = [_nonnegative_int(row.get("replyLength")) for row in rows]
    reaction_turns = sum(bool(row.get("reactions")) for row in rows)
    selected_media_turns = sum(_media_type(row) != "none" for row in rows)
    sent_media_turns = sum(bool(_media(row).get("url")) for row in rows)
    inbound_media_turns = sum(_nonnegative_int(row.get("inboundMediaCount")) > 0 for row in rows)
    inbound_media_action_turns = sum(
        _nonnegative_int(row.get("inboundMediaCount")) > 0
        and (bool(row.get("reactions")) or _media_type(row) != "none")
        for row in rows
    )
    return TurnMetrics(
        turn_count=len(rows),
        parse_statuses=dict(sorted(parse_statuses.items())),
        reply_over_120=sum(length > _REPLY_LENGTH_120 for length in reply_lengths),
        reply_over_180=sum(length > _REPLY_LENGTH_180 for length in reply_lengths),
        reply_over_200=sum(length > _REPLY_LENGTH_200 for length in reply_lengths),
        reaction_turns=reaction_turns,
        selected_media_turns=selected_media_turns,
        sent_media_turns=sent_media_turns,
        inbound_media_turns=inbound_media_turns,
        inbound_media_action_turns=inbound_media_action_turns,
        silence_turns=sum(str(row.get("intent") or "") == "silence" for row in rows),
    )


def summarize_archive(path: Path) -> TurnMetrics:
    """Read only turn-decision payloads from an archive and aggregate their signals."""
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT payload_json FROM training_events WHERE event_type = ?",
            ("mikav2_turn_decision",),
        ).fetchall()
    payloads: list[Mapping[str, Any]] = []
    for (raw_payload,) in rows:
        try:
            payload = json.loads(raw_payload)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(payload, Mapping):
            payloads.append(payload)
    return summarize_turn_payloads(payloads)


def _media(row: Mapping[str, Any]) -> Mapping[str, Any]:
    media = row.get("media")
    return media if isinstance(media, Mapping) else {}


def _media_type(row: Mapping[str, Any]) -> str:
    return str(_media(row).get("type") or "none")


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
