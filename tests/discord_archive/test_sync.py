from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from mika_archive.config import ArchiveConfig
from mika_archive.database import ArchiveDatabase
from mika_archive.export import Exporter
from mika_archive.resources import DownloadResult
from mika_archive.sync import ArchiveSynchronizer


class FakeDiscord:
    def __init__(self) -> None:
        self.permission_errors: list[dict[str, object]] = []
        self.after_values: list[str | None] = []

    def guilds(self):
        return [{"id": "1", "name": "guild"}]

    def discover_targets(self, guild_id):
        return [{"id": "2", "guild_id": "1", "name": "general", "type": 0}]

    def iter_history(self, channel_id, *, after=None, before=None, limit=None):
        self.after_values.append(after)
        if after is None:
            return iter(
                [
                    {
                        "id": "10",
                        "channel_id": "2",
                        "content": "hello",
                        "timestamp": "2026-08-01T00:00:00+00:00",
                        "author": {"id": "3", "username": "a"},
                        "attachments": [],
                        "embeds": [],
                        "sticker_items": [],
                    }
                ]
            )
        return iter([])


class SyncTests(unittest.TestCase):
    def test_second_incremental_sync_uses_saved_cursor_and_does_not_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = ArchiveConfig.for_root(Path(temp))
            db = ArchiveDatabase(config.database_path)
            db.initialize()
            discord = FakeDiscord()
            sync = ArchiveSynchronizer(config, db, discord)
            sync.run(full=True, download_resources=False, reconcile=False)
            sync.run(full=False, download_resources=False, reconcile=False)
            self.assertEqual(discord.after_values, [None, "10"])
            self.assertEqual(
                db.connection.execute("SELECT count(*) FROM messages").fetchone()[0], 1
            )
            db.close()

    def test_parallel_download_phase_processes_each_pending_resource_once(self) -> None:
        class FakeDownloader:
            def download(self, url):
                return DownloadResult(
                    "stored", url, 200, "text/plain", 1, "a" * 64, Path("/tmp/blob")
                )

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as temp:
            config = ArchiveConfig.for_root(Path(temp))
            db = ArchiveDatabase(config.database_path)
            db.initialize()
            for index in range(17):
                db.connection.execute(
                    "INSERT INTO resources(canonical_url,source_kind,status,discovered_at) VALUES(?, 'external_url', 'pending', 'now')",
                    (f"https://example.com/{index}",),
                )
            db.connection.commit()
            sync = ArchiveSynchronizer(config, db, FakeDiscord(), downloader_factory=FakeDownloader)
            report = sync.download_only(workers=4)
            self.assertEqual(report.resources_stored, 17)
            self.assertEqual(
                db.connection.execute(
                    "SELECT count(*) FROM resources WHERE status='stored'"
                ).fetchone()[0],
                17,
            )
            db.close()

    def test_export_is_deterministic_and_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = ArchiveConfig.for_root(Path(temp))
            db = ArchiveDatabase(config.database_path)
            db.initialize()
            ArchiveSynchronizer(config, db, FakeDiscord()).run(
                full=True, download_resources=False, reconcile=False
            )
            first = Exporter(config, db).write()
            bytes_one = first.messages.read_bytes()
            second = Exporter(config, db).write()
            self.assertEqual(bytes_one, second.messages.read_bytes())
            with gzip.open(second.messages, "rt", encoding="utf-8") as stream:
                self.assertEqual(json.loads(stream.readline())["message_id"], "10")
            db.close()


if __name__ == "__main__":
    unittest.main()
