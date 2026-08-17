"""Read-only access to validated messages in the shared Discord archive."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from mika.persistence.conversations.relationship_integrity import normalize_discord_message_id
from mika.persistence.conversations.relationship_records import ArchiveCursor, ArchiveSourceRecord

_VISIBILITY_KINDS = {"direct_message", "guild", "channel", "global_explicit"}


@dataclass(frozen=True, slots=True)
class ArchivePage:
    """Validated archive rows plus a content-free corruption count."""

    records: tuple[ArchiveSourceRecord, ...]
    invalid_records: int = 0


class ArchiveReader:
    """Read archive messages without mutating the separately retained database."""

    def __init__(self, path: Path, *, source_name: str = "shared_archive") -> None:
        self._path = path
        self._source_name = source_name

    def iter_after(self, cursor: ArchiveCursor | None, limit: int) -> list[ArchiveSourceRecord]:
        """Return validated rows after the cursor in strict compound order."""
        return list(self.scan_after(cursor, limit).records)

    def scan_after(self, cursor: ArchiveCursor | None, limit: int) -> ArchivePage:
        """Return a page and report rows excluded for invalid ordering fields."""
        if limit < 1:
            return ArchivePage(())
        if cursor is not None and cursor.source_name != self._source_name:
            raise ValueError("archive cursor belongs to another source")
        records, invalid_records = self._read_records(cursor, limit)
        return ArchivePage(tuple(records), invalid_records)

    def _read_records(
        self, cursor: ArchiveCursor | None, limit: int
    ) -> tuple[list[ArchiveSourceRecord], int]:
        uri = f"file:{quote(str(self._path.resolve()))}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(messages)").fetchall()
            }
            required = {"id", "author_id", "content", "created_at", "guild_id", "channel_id"}
            if not required.issubset(columns):
                raise ValueError("archive messages table is missing required columns")
            author = "author" if "author" in columns else "author_name AS author"
            message_id = (
                "discord_message_id"
                if "discord_message_id" in columns
                else "id AS discord_message_id"
            )
            message_id_column = "discord_message_id" if "discord_message_id" in columns else "id"
            metadata = "metadata_json" if "metadata_json" in columns else "'{}' AS metadata_json"
            valid = (
                f"{message_id_column} != '' AND "
                f"{message_id_column} NOT GLOB '*[^0-9]*' AND "
                "julianday(created_at) IS NOT NULL AND "
                "(created_at LIKE '%Z' OR instr(substr(created_at,20), '+') > 0 OR "
                "instr(substr(created_at,20), '-') > 0)"
            )
            continuation = ""
            parameters: list[object] = []
            if cursor is not None:
                cursor_message_id = normalize_discord_message_id(cursor.discord_message_id)
                cursor_timestamp = cursor.archive_created_at.astimezone(UTC).isoformat()
                continuation = (
                    " AND (julianday(created_at) > julianday(?) OR "
                    "(julianday(created_at) = julianday(?) AND "
                    f"CAST({message_id_column} AS INTEGER) "
                    "> CAST(? AS INTEGER)))"
                )
                parameters.extend([cursor_timestamp, cursor_timestamp, cursor_message_id])
            parameters.append(limit)
            rows = connection.execute(
                f"SELECT id,{author},author_id,content,created_at,guild_id,channel_id,"  # noqa: S608
                f"{message_id},{metadata} FROM messages WHERE {valid}{continuation} "
                f"ORDER BY julianday(created_at),CAST({message_id_column} AS INTEGER) LIMIT ?",
                parameters,
            ).fetchall()
            invalid_records = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM messages WHERE NOT ({valid})"  # noqa: S608
                ).fetchone()[0]
            )
        records = [record for row in rows if (record := self._record(row)) is not None]
        return records, invalid_records + len(rows) - len(records)

    def _record(self, row: sqlite3.Row) -> ArchiveSourceRecord | None:
        try:
            message_id = normalize_discord_message_id(str(row["discord_message_id"] or ""))
        except ValueError:
            return None
        created_at = _utc_timestamp(str(row["created_at"] or ""))
        if created_at is None:
            return None
        guild_id = _optional_string(row["guild_id"])
        channel_id = _optional_string(row["channel_id"])
        return ArchiveSourceRecord(
            source_kind=self._source_name,
            source_id=str(row["id"]),
            discord_message_id=message_id,
            author_id=str(row["author_id"] or ""),
            author_name=str(row["author"] or ""),
            text=str(row["content"] or ""),
            archive_created_at=created_at,
            visibility_kind=_visibility(row["metadata_json"], guild_id),
            guild_id=guild_id,
            channel_id=channel_id,
        )


def _utc_timestamp(raw: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _visibility(raw_metadata: object, guild_id: str | None) -> str:
    try:
        metadata = json.loads(str(raw_metadata or "{}"))
    except json.JSONDecodeError:
        metadata = {}
    value = metadata.get("visibility_kind") if isinstance(metadata, dict) else None
    if isinstance(value, str) and value in _VISIBILITY_KINDS:
        return value
    return "direct_message" if guild_id is None else "channel"
