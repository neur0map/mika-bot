from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mika_archive.config import ArchiveConfig
from mika_archive.database import ArchiveDatabase
from mika_archive.verify import Verifier


class VerifyTests(unittest.TestCase):
    def test_detects_altered_content_addressed_blob(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = ArchiveConfig.for_root(Path(temp))
            db = ArchiveDatabase(config.database_path)
            db.initialize()
            blob = config.media_dir / "aa" / ("a" * 64)
            blob.parent.mkdir(parents=True)
            blob.write_bytes(b"wrong")
            db.connection.execute(
                "INSERT INTO resources(canonical_url,source_kind,status,byte_count,sha256,storage_path,discovered_at) VALUES(?,?,?,?,?,?,?)",
                ("https://example.com/a", "external_url", "stored", 5, "a" * 64, str(blob), "now"),
            )
            db.connection.commit()
            report = Verifier(config, db).run()
            self.assertFalse(report.ok)
            self.assertEqual(report.bad_blobs, 1)
            db.close()

    def test_clean_empty_archive_passes_local_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = ArchiveConfig.for_root(Path(temp))
            db = ArchiveDatabase(config.database_path)
            db.initialize()
            report = Verifier(config, db).run()
            self.assertTrue(report.ok)
            db.close()


if __name__ == "__main__":
    unittest.main()
