from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from mika_archive.database import ArchiveDatabase
from mika_archive.ingest import MessageIngester
from mika_archive.raw_store import RawStore


class IngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db = ArchiveDatabase(root / "archive.sqlite3")
        self.db.initialize()
        self.db.upsert_channel({"id": "22", "guild_id": "44", "name": "general", "type": 0})
        self.store = RawStore(root / "raw")
        self.ingester = MessageIngester(self.db, self.store)

    def tearDown(self) -> None:
        self.db.close()
        self.temp.cleanup()

    def message(self, content: str = "see https://example.com/a.gif") -> dict[str, object]:
        return {
            "id": "101",
            "channel_id": "22",
            "content": content,
            "timestamp": "2026-08-01T12:00:00+00:00",
            "type": 0,
            "author": {"id": "33", "username": "alice", "bot": False},
            "attachments": [
                {
                    "id": "7",
                    "url": "https://cdn.discordapp.com/a.png",
                    "filename": "a.png",
                    "size": 12,
                    "content_type": "image/png",
                }
            ],
            "embeds": [],
            "sticker_items": [],
        }

    def test_ingest_writes_parseable_raw_snapshot_resources_and_cursor(self) -> None:
        result = self.ingester.ingest_page(
            "44", {"id": "22", "guild_id": "44", "name": "general", "type": 0}, [self.message()]
        )
        self.assertEqual(result.new_messages, 1)
        row = self.db.connection.execute(
            "SELECT highest_message_id FROM cursors WHERE channel_id='22'"
        ).fetchone()
        self.assertEqual(row[0], "101")
        resources = self.db.connection.execute(
            "SELECT canonical_url,source_kind FROM resources ORDER BY canonical_url"
        ).fetchall()
        self.assertEqual(
            [(x[0], x[1]) for x in resources],
            [
                ("https://cdn.discordapp.com/a.png", "discord_attachment"),
                ("https://example.com/a.gif", "external_url"),
            ],
        )
        snap = self.db.connection.execute("SELECT raw_path FROM snapshots").fetchone()[0]
        with gzip.open(snap, "rt", encoding="utf-8") as stream:
            self.assertEqual(json.loads(stream.readline())["id"], "101")

    def test_identical_reconciliation_does_not_duplicate_snapshot_or_message(self) -> None:
        self.ingester.ingest_page(
            "44", {"id": "22", "guild_id": "44", "name": "general", "type": 0}, [self.message()]
        )
        self.ingester.ingest_page(
            "44", {"id": "22", "guild_id": "44", "name": "general", "type": 0}, [self.message()]
        )
        self.assertEqual(
            self.db.connection.execute("SELECT count(*) FROM messages").fetchone()[0], 1
        )
        self.assertEqual(
            self.db.connection.execute("SELECT count(*) FROM snapshots").fetchone()[0], 1
        )

    def test_edit_adds_snapshot_and_preserves_first_version(self) -> None:
        self.ingester.ingest_page(
            "44",
            {"id": "22", "guild_id": "44", "name": "general", "type": 0},
            [self.message("before")],
        )
        changed = self.message("after")
        changed["edited_timestamp"] = "2026-08-02T00:00:00+00:00"
        self.ingester.ingest_page(
            "44", {"id": "22", "guild_id": "44", "name": "general", "type": 0}, [changed]
        )
        row = self.db.connection.execute(
            "SELECT content,first_raw_json FROM messages WHERE id='101'"
        ).fetchone()
        self.assertEqual(row[0], "after")
        self.assertIn('"content":"before"', row[1])
        self.assertEqual(
            self.db.connection.execute("SELECT count(*) FROM snapshots").fetchone()[0], 2
        )


if __name__ == "__main__":
    unittest.main()
