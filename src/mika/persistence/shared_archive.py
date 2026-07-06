"""Shared Mika archive writer for A/B training logs with the JS bot."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from mika.core.config import get_settings
from mika.core.logging import get_logger

logger = get_logger(__name__)


def _now_id(prefix: str) -> str:
    return f"py-{prefix}-{time.time_ns()}"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=5)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY,
          role TEXT,
          author TEXT,
          author_id TEXT,
          content TEXT,
          created_at TEXT,
          guild_id TEXT,
          guild_name TEXT,
          channel_id TEXT,
          channel_name TEXT,
          discord_message_id TEXT,
          reply_to_discord_message_id TEXT,
          media_json TEXT,
          reactions_json TEXT,
          metadata_json TEXT
        );
        CREATE TABLE IF NOT EXISTS training_events (
          id TEXT PRIMARY KEY,
          event_type TEXT NOT NULL,
          created_at TEXT NOT NULL,
          guild_id TEXT,
          guild_name TEXT,
          channel_id TEXT,
          channel_name TEXT,
          discord_message_id TEXT,
          related_discord_message_id TEXT,
          author TEXT,
          author_id TEXT,
          emoji TEXT,
          payload_json TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
          content,
          author,
          channel_id UNINDEXED,
          message_id UNINDEXED,
          tokenize = 'unicode61'
        );
        CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
        CREATE INDEX IF NOT EXISTS idx_training_events_created_at ON training_events(created_at);
        """
    )
    for stmt in (
        "ALTER TABLE messages ADD COLUMN guild_name TEXT",
        "ALTER TABLE messages ADD COLUMN channel_name TEXT",
        "ALTER TABLE messages ADD COLUMN reactions_json TEXT",
        "ALTER TABLE messages ADD COLUMN metadata_json TEXT",
    ):
        try:
            con.execute(stmt)
        except sqlite3.OperationalError as error:
            if "duplicate column" not in str(error).lower():
                raise
    return con


def _archive_message_sync(record: dict[str, Any]) -> None:
    path = get_settings().shared_archive_path
    if not path:
        return
    with _connect(path) as con:
        row = {
            "id": record.get("id") or _now_id("msg"),
            "role": record.get("role"),
            "author": record.get("author"),
            "author_id": record.get("author_id"),
            "content": str(record.get("content") or "")[:4000],
            "created_at": record.get("created_at"),
            "guild_id": record.get("guild_id"),
            "guild_name": record.get("guild_name"),
            "channel_id": record.get("channel_id"),
            "channel_name": record.get("channel_name"),
            "discord_message_id": record.get("discord_message_id"),
            "reply_to_discord_message_id": record.get("reply_to_discord_message_id"),
            "media_json": json.dumps(record.get("media") or []),
            "reactions_json": json.dumps(record.get("reactions") or []),
            "metadata_json": json.dumps(record.get("metadata") or {}),
        }
        con.execute(
            """
            INSERT OR REPLACE INTO messages
            (id, role, author, author_id, content, created_at, guild_id, guild_name,
             channel_id, channel_name, discord_message_id, reply_to_discord_message_id,
             media_json, reactions_json, metadata_json)
            VALUES
            (:id, :role, :author, :author_id, :content, :created_at, :guild_id, :guild_name,
             :channel_id, :channel_name, :discord_message_id, :reply_to_discord_message_id,
             :media_json, :reactions_json, :metadata_json)
            """,
            row,
        )
        con.execute("DELETE FROM messages_fts WHERE message_id = ?", (row["id"],))
        con.execute(
            "INSERT INTO messages_fts(content, author, channel_id, message_id) VALUES (?, ?, ?, ?)",
            (row["content"], row["author"] or "", row["channel_id"] or "", row["id"]),
        )


def _archive_event_sync(event: dict[str, Any]) -> None:
    path = get_settings().shared_archive_path
    if not path:
        return
    with _connect(path) as con:
        row = {
            "id": event.get("id") or _now_id("event"),
            "event_type": event.get("event_type") or "event",
            "created_at": event.get("created_at"),
            "guild_id": event.get("guild_id"),
            "guild_name": event.get("guild_name"),
            "channel_id": event.get("channel_id"),
            "channel_name": event.get("channel_name"),
            "discord_message_id": event.get("discord_message_id"),
            "related_discord_message_id": event.get("related_discord_message_id"),
            "author": event.get("author"),
            "author_id": event.get("author_id"),
            "emoji": event.get("emoji"),
            "payload_json": json.dumps(event.get("payload") or {}),
        }
        con.execute(
            """
            INSERT OR REPLACE INTO training_events
            (id, event_type, created_at, guild_id, guild_name, channel_id, channel_name,
             discord_message_id, related_discord_message_id, author, author_id, emoji, payload_json)
            VALUES
            (:id, :event_type, :created_at, :guild_id, :guild_name, :channel_id, :channel_name,
             :discord_message_id, :related_discord_message_id, :author, :author_id, :emoji,
             :payload_json)
            """,
            row,
        )


async def archive_message(record: dict[str, Any]) -> None:
    """Persist one Discord message in the shared JS-compatible archive."""
    try:
        await asyncio.to_thread(_archive_message_sync, record)
    except Exception as error:
        logger.warning("shared archive message write failed: %s", error)


async def archive_event(event: dict[str, Any]) -> None:
    """Persist one behavioral event in the shared JS-compatible archive."""
    try:
        await asyncio.to_thread(_archive_event_sync, event)
    except Exception as error:
        logger.warning("shared archive event write failed: %s", error)
