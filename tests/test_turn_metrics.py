"""Privacy-safe aggregate conversation metric tests."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from pathlib import Path

from mika.ai.learning.metrics import summarize_archive, summarize_turn_payloads


def test_summarize_turn_payloads_counts_quality_signals_without_text() -> None:
    metrics = summarize_turn_payloads(
        [
            {
                "replyLength": 42,
                "parseStatus": "strict_json",
                "intent": "joke",
                "reactions": ["💀"],
                "media": {"type": "none", "url": None},
                "inboundMediaCount": 0,
            },
            {
                "replyLength": 201,
                "parseStatus": "plain_fallback",
                "intent": "chat",
                "reactions": [],
                "media": {"type": "gif", "url": None},
                "inboundMediaCount": 1,
            },
            {
                "replyLength": 0,
                "parseStatus": "strict_json",
                "intent": "silence",
                "reactions": [],
                "media": {"type": "none", "url": None},
                "inboundMediaCount": 1,
            },
        ]
    )

    assert metrics.turn_count == 3
    assert metrics.parse_statuses == {"plain_fallback": 1, "strict_json": 2}
    assert metrics.reply_over_120 == 1
    assert metrics.reply_over_180 == 1
    assert metrics.reply_over_200 == 1
    assert metrics.reaction_turns == 1
    assert metrics.selected_media_turns == 1
    assert metrics.sent_media_turns == 0
    assert metrics.inbound_media_turns == 2
    assert metrics.inbound_media_action_turns == 1
    assert metrics.silence_turns == 1
    assert "reply" not in asdict(metrics)
    assert "content" not in asdict(metrics)


def test_summarize_archive_reads_only_turn_decision_payloads(tmp_path: Path) -> None:
    path = tmp_path / "archive.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE training_events (event_type TEXT, created_at TEXT, payload_json TEXT)"
        )
        connection.execute(
            "INSERT INTO training_events VALUES (?, ?, ?)",
            ("mikav2_turn_decision", "2026-07-21T00:00:00+00:00", '{"replyLength": 12}'),
        )
        connection.execute(
            "INSERT INTO training_events VALUES (?, ?, ?)",
            ("discord_reaction", "2026-07-21T00:00:01+00:00", '{"emoji":"💀"}'),
        )

    metrics = summarize_archive(path)

    assert metrics.turn_count == 1
    assert metrics.reply_over_120 == 0
