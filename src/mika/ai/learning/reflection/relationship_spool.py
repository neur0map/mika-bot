"""Durable local spool for accepted relationship observations."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from mika.conversation.relationships.service import ObservationInput


class RelationshipObservationSpool:
    """Persist pending observations across process restarts."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS pending_observations (
                    message_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    dead_letter INTEGER NOT NULL DEFAULT 0,
                    last_failure TEXT
                )"""
            )

    def put(self, observation: ObservationInput) -> None:
        payload = asdict(observation)
        payload["created_at"] = observation.created_at.isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO pending_observations(message_id, payload_json)
                   VALUES (?, ?)""",
                (observation.message_id, json.dumps(payload, sort_keys=True)),
            )

    def pending(self, limit: int) -> tuple[ObservationInput, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT payload_json FROM pending_observations
                   WHERE dead_letter = 0 ORDER BY rowid LIMIT ?""",
                (limit,),
            ).fetchall()
        return tuple(self._decode(str(row[0])) for row in rows)

    def complete(self, message_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM pending_observations WHERE message_id = ?", (message_id,)
            )

    def fail(self, message_id: str, reason: str, *, max_attempts: int) -> bool:
        with self._connect() as connection:
            connection.execute(
                """UPDATE pending_observations
                   SET attempts = attempts + 1,
                       dead_letter = CASE WHEN attempts + 1 >= ? THEN 1 ELSE 0 END,
                       last_failure = ?
                   WHERE message_id = ?""",
                (max_attempts, reason[:120], message_id),
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
