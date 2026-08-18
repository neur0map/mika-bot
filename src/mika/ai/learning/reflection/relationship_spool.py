"""Durable local spool for accepted relationship observations."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mika.conversation.relationships.service import ObservationInput


class RelationshipObservationSpool:
    """Persist pending observations across process restarts."""

    def __init__(self, path: Path, *, ttl_seconds: float = 86_400.0) -> None:
        if ttl_seconds <= 0:
            raise ValueError("spool ttl must be positive")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._ttl_seconds = ttl_seconds
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS pending_observations (
                    message_id TEXT PRIMARY KEY,
                    payload_json TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    dead_letter INTEGER NOT NULL DEFAULT 0,
                    last_failure TEXT,
                    next_attempt_at TEXT,
                    expires_at TEXT
                )"""
            )
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(pending_observations)").fetchall()
            }
            for name in ("next_attempt_at", "expires_at"):
                if name not in columns:
                    connection.execute(f"ALTER TABLE pending_observations ADD COLUMN {name} TEXT")
            now = datetime.now(UTC).isoformat()
            connection.execute(
                "UPDATE pending_observations SET next_attempt_at = ? WHERE next_attempt_at IS NULL",
                (now,),
            )
            connection.execute(
                "UPDATE pending_observations SET expires_at = ? WHERE expires_at IS NULL",
                (now,),
            )
            connection.execute(
                """UPDATE pending_observations SET payload_json = NULL
                   WHERE dead_letter = 1 AND expires_at <= ?""",
                (now,),
            )
            connection.execute(
                """DELETE FROM pending_observations
                   WHERE dead_letter = 0 AND expires_at <= ?""",
                (now,),
            )
        path.chmod(0o600)

    def put(self, observation: ObservationInput) -> None:
        payload = asdict(observation)
        payload["created_at"] = observation.created_at.isoformat()
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO pending_observations(
                       message_id, payload_json, next_attempt_at, expires_at
                   ) VALUES (?, ?, ?, ?)""",
                (
                    observation.message_id,
                    json.dumps(payload, sort_keys=True),
                    now.isoformat(),
                    (now + timedelta(seconds=self._ttl_seconds)).isoformat(),
                ),
            )

    def pending(
        self, limit: int, *, excluding: frozenset[str] = frozenset()
    ) -> tuple[ObservationInput, ...]:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """UPDATE pending_observations SET payload_json = NULL
                   WHERE dead_letter = 1 AND expires_at IS NOT NULL AND expires_at <= ?""",
                (now,),
            )
            connection.execute(
                """DELETE FROM pending_observations
                   WHERE dead_letter = 0 AND expires_at IS NOT NULL AND expires_at <= ?""",
                (now,),
            )
            rows = connection.execute(
                """SELECT message_id, payload_json FROM pending_observations
                   WHERE dead_letter = 0 AND payload_json IS NOT NULL
                     AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                   ORDER BY rowid LIMIT ?""",
                (now, limit + len(excluding)),
            ).fetchall()
        return tuple(self._decode(str(row[1])) for row in rows if str(row[0]) not in excluding)[
            :limit
        ]

    def complete(self, message_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM pending_observations WHERE message_id = ?", (message_id,)
            )

    def fail(
        self,
        message_id: str,
        reason: str,
        *,
        max_attempts: int,
        backoff_seconds: float,
    ) -> bool:
        next_attempt = (datetime.now(UTC) + timedelta(seconds=backoff_seconds)).isoformat()
        with self._connect() as connection:
            connection.execute(
                """UPDATE pending_observations
                   SET attempts = attempts + 1,
                       dead_letter = CASE WHEN attempts + 1 >= ? THEN 1 ELSE 0 END,
                       payload_json = CASE WHEN attempts + 1 >= ? THEN '{}' ELSE payload_json END,
                       last_failure = ?,
                       next_attempt_at = ?
                   WHERE message_id = ?""",
                (max_attempts, max_attempts, reason[:120], next_attempt, message_id),
            )
            row = connection.execute(
                "SELECT dead_letter FROM pending_observations WHERE message_id = ?", (message_id,)
            ).fetchone()
        return bool(row and row[0])

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    @staticmethod
    def _decode(payload: str) -> ObservationInput:
        values = json.loads(payload)
        values["created_at"] = datetime.fromisoformat(values["created_at"])
        return ObservationInput(**values)
