from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS guilds (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, raw_json TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    guild_id TEXT NOT NULL,
    parent_id TEXT,
    name TEXT NOT NULL DEFAULT '',
    type INTEGER NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0,
    raw_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(guild_id) REFERENCES guilds(id)
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    guild_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    author_id TEXT NOT NULL DEFAULT '',
    author_name TEXT NOT NULL DEFAULT '',
    author_bot INTEGER NOT NULL DEFAULT 0,
    message_type INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    edited_at TEXT,
    referenced_message_id TEXT,
    flags INTEGER NOT NULL DEFAULT 0,
    first_raw_json TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    FOREIGN KEY(guild_id) REFERENCES guilds(id),
    FOREIGN KEY(channel_id) REFERENCES channels(id)
);
CREATE INDEX IF NOT EXISTS messages_channel_created ON messages(channel_id, created_at, id);
CREATE INDEX IF NOT EXISTS messages_author ON messages(author_id, created_at);
CREATE TABLE IF NOT EXISTS cursors (
    channel_id TEXT PRIMARY KEY,
    highest_message_id TEXT,
    last_success_at TEXT,
    last_error TEXT,
    FOREIGN KEY(channel_id) REFERENCES channels(id)
);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    raw_sha256 TEXT NOT NULL,
    raw_path TEXT NOT NULL,
    raw_offset INTEGER,
    recorded_at TEXT NOT NULL,
    UNIQUE(message_id, raw_sha256),
    FOREIGN KEY(message_id) REFERENCES messages(id)
);
CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_url TEXT NOT NULL UNIQUE,
    source_kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    http_status INTEGER,
    final_url TEXT,
    mime_type TEXT,
    byte_count INTEGER,
    sha256 TEXT,
    storage_path TEXT,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    discovered_at TEXT NOT NULL,
    attempted_at TEXT,
    stored_at TEXT
);
CREATE INDEX IF NOT EXISTS resources_status ON resources(status, id);
CREATE INDEX IF NOT EXISTS resources_sha ON resources(sha256);
CREATE TABLE IF NOT EXISTS message_resources (
    message_id TEXT NOT NULL,
    resource_id INTEGER NOT NULL,
    relation TEXT NOT NULL,
    original_name TEXT,
    declared_size INTEGER,
    declared_mime TEXT,
    PRIMARY KEY(message_id, resource_id, relation),
    FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY(resource_id) REFERENCES resources(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    report_json TEXT NOT NULL DEFAULT '{}'
);
"""


class ArchiveDatabase:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.row_factory = sqlite3.Row

    def initialize(self) -> None:
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connection:
            yield self.connection

    def upsert_guild(self, guild: dict[str, Any], *, commit: bool = True) -> None:
        now = _now()
        self.connection.execute(
            "INSERT INTO guilds(id,name,raw_json,updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name,raw_json=excluded.raw_json,updated_at=excluded.updated_at",
            (str(guild["id"]), str(guild.get("name", "")), canonical_json(guild), now),
        )
        if commit:
            self.connection.commit()

    def upsert_channel(self, channel: dict[str, Any], *, commit: bool = True) -> None:
        guild_id = str(channel["guild_id"])
        self.connection.execute(
            "INSERT OR IGNORE INTO guilds(id,name,raw_json,updated_at) VALUES(?,?,?,?)",
            (guild_id, "", "{}", _now()),
        )
        self.connection.execute(
            "INSERT INTO channels(id,guild_id,parent_id,name,type,archived,raw_json,updated_at) VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET guild_id=excluded.guild_id,parent_id=excluded.parent_id,name=excluded.name,type=excluded.type,archived=excluded.archived,raw_json=excluded.raw_json,updated_at=excluded.updated_at",
            (
                str(channel["id"]),
                guild_id,
                _string_or_none(channel.get("parent_id")),
                str(channel.get("name", "")),
                int(channel.get("type", 0)),
                int(bool(channel.get("thread_metadata", {}).get("archived", False))),
                canonical_json(channel),
                _now(),
            ),
        )
        if commit:
            self.connection.commit()

    def upsert_message(
        self, guild_id: str, channel_id: str, message: dict[str, Any], *, commit: bool = True
    ) -> None:
        raw = canonical_json(message)
        now = _now()
        author = message.get("author") or {}
        referenced = message.get("message_reference") or {}
        values = (
            str(message["id"]),
            guild_id,
            channel_id,
            str(author.get("id", "")),
            str(author.get("global_name") or author.get("username") or ""),
            int(bool(author.get("bot"))),
            int(message.get("type", 0)),
            str(message.get("content") or ""),
            str(message.get("timestamp") or now),
            _string_or_none(message.get("edited_timestamp")),
            _string_or_none(referenced.get("message_id")),
            int(message.get("flags", 0)),
            raw,
            raw,
            now,
            now,
        )
        self.connection.execute(
            "INSERT INTO messages(id,guild_id,channel_id,author_id,author_name,author_bot,message_type,content,created_at,edited_at,referenced_message_id,flags,first_raw_json,raw_json,first_seen_at,last_seen_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET author_id=excluded.author_id,author_name=excluded.author_name,author_bot=excluded.author_bot,message_type=excluded.message_type,content=excluded.content,edited_at=excluded.edited_at,referenced_message_id=excluded.referenced_message_id,flags=excluded.flags,raw_json=excluded.raw_json,last_seen_at=excluded.last_seen_at",
            values,
        )
        if commit:
            self.connection.commit()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _string_or_none(value: object) -> str | None:
    return None if value is None else str(value)
