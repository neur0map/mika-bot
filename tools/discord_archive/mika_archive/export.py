from __future__ import annotations

import gzip
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mika_archive.config import ArchiveConfig
from mika_archive.database import ArchiveDatabase


@dataclass(frozen=True, slots=True)
class ExportPaths:
    messages: Path
    resources: Path


class Exporter:
    def __init__(self, config: ArchiveConfig, database: ArchiveDatabase) -> None:
        self.config = config
        self.db = database

    def write(self) -> ExportPaths:
        self.config.exports_dir.mkdir(parents=True, exist_ok=True)
        messages = self.config.exports_dir / "messages.jsonl.gz"
        resources = self.config.exports_dir / "resources.jsonl.gz"
        self._write_messages(messages)
        self._write_resources(resources)
        return ExportPaths(messages, resources)

    def _write_messages(self, path: Path) -> None:
        rows = self.db.connection.execute(
            "SELECT m.*,c.name AS channel_name,c.parent_id,g.name AS guild_name FROM messages m JOIN channels c ON c.id=m.channel_id JOIN guilds g ON g.id=m.guild_id ORDER BY CAST(m.id AS INTEGER)"
        )

        def records():
            for row in rows:
                yield {
                    "message_id": row["id"],
                    "guild_id": row["guild_id"],
                    "guild_name": row["guild_name"],
                    "channel_id": row["channel_id"],
                    "channel_name": row["channel_name"],
                    "thread_parent_id": row["parent_id"],
                    "author_id": row["author_id"],
                    "author_name": row["author_name"],
                    "author_bot": bool(row["author_bot"]),
                    "message_type": row["message_type"],
                    "content": row["content"],
                    "created_at": row["created_at"],
                    "edited_at": row["edited_at"],
                    "reply_to_message_id": row["referenced_message_id"],
                    "flags": row["flags"],
                    "raw": json.loads(row["raw_json"]),
                }

        _write_deterministic_gzip(path, records())

    def _write_resources(self, path: Path) -> None:
        rows = self.db.connection.execute(
            "SELECT r.*,mr.message_id,mr.relation,mr.original_name,mr.declared_size,mr.declared_mime FROM resources r LEFT JOIN message_resources mr ON mr.resource_id=r.id ORDER BY r.id,mr.message_id,mr.relation"
        )
        _write_deterministic_gzip(path, (dict(row) for row in rows))


def _write_deterministic_gzip(path: Path, records) -> None:
    descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as zipped:
                for record in records:
                    zipped.write(
                        (
                            json.dumps(
                                record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                            )
                            + "\n"
                        ).encode()
                    )
            raw.flush()
            os.fsync(raw.fileno())
        Path(temp_name).replace(path)
    finally:
        Path(temp_name).unlink(missing_ok=True)
