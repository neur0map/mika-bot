from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mika_archive.config import ArchiveConfig
from mika_archive.database import ArchiveDatabase


class ConfigTests(unittest.TestCase):
    def test_defaults_are_rooted_under_archive_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = ArchiveConfig.for_root(Path(temp))
            self.assertEqual(config.database_path, Path(temp) / "data/archive.sqlite3")
            self.assertEqual(config.media_dir, Path(temp) / "data/media/sha256")
            self.assertEqual(config.max_resource_bytes, 512 * 1024 * 1024)


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "archive.sqlite3"
        self.db = ArchiveDatabase(self.path)
        self.db.initialize()

    def tearDown(self) -> None:
        self.db.close()
        self.temp.cleanup()

    def test_enables_wal_and_foreign_keys(self) -> None:
        self.assertEqual(self.db.connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(self.db.connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_message_upsert_is_idempotent_and_preserves_first_raw_record(self) -> None:
        first = {
            "id": "11",
            "channel_id": "22",
            "content": "before",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "author": {"id": "33", "username": "u"},
        }
        edited = {**first, "content": "after", "edited_timestamp": "2026-01-02T00:00:00+00:00"}
        self.db.upsert_channel({"id": "22", "guild_id": "44", "name": "general", "type": 0})
        self.db.upsert_message("44", "22", first)
        self.db.upsert_message("44", "22", edited)
        row = self.db.connection.execute(
            "SELECT content, first_raw_json, raw_json FROM messages WHERE id='11'"
        ).fetchone()
        self.assertEqual(row["content"], "after")
        self.assertIn('"content":"before"', row["first_raw_json"])
        self.assertIn('"content":"after"', row["raw_json"])
        self.assertEqual(
            self.db.connection.execute("SELECT count(*) FROM messages").fetchone()[0], 1
        )

    def test_foreign_key_check_is_clean(self) -> None:
        self.assertEqual(self.db.connection.execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
