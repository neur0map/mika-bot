from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from mika_archive.config import ArchiveConfig
from mika_archive.database import ArchiveDatabase


@dataclass(slots=True)
class VerificationReport:
    ok: bool = True
    database_integrity: str = "ok"
    foreign_key_errors: int = 0
    messages: int = 0
    snapshots: int = 0
    raw_records: int = 0
    raw_errors: int = 0
    stored_resources: int = 0
    failed_resources: int = 0
    skipped_resources: int = 0
    pending_resources: int = 0
    bad_blobs: int = 0
    export_records: int = 0
    export_errors: int = 0
    online_messages: int | None = None
    online_delta: int | None = None
    permission_errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Verifier:
    def __init__(
        self, config: ArchiveConfig, database: ArchiveDatabase, discord: Any | None = None
    ) -> None:
        self.config = config
        self.db = database
        self.discord = discord

    def run(self, *, online: bool = False) -> VerificationReport:
        report = VerificationReport()
        integrity = self.db.connection.execute("PRAGMA integrity_check").fetchone()[0]
        report.database_integrity = str(integrity)
        report.foreign_key_errors = len(
            self.db.connection.execute("PRAGMA foreign_key_check").fetchall()
        )
        report.messages = self.db.connection.execute("SELECT count(*) FROM messages").fetchone()[0]
        report.snapshots = self.db.connection.execute("SELECT count(*) FROM snapshots").fetchone()[
            0
        ]
        self._verify_raw(report)
        self._verify_blobs(report)
        self._verify_exports(report)
        if online:
            self._verify_online(report)
        report.ok = all(
            (
                report.database_integrity == "ok",
                report.foreign_key_errors == 0,
                report.raw_errors == 0,
                report.bad_blobs == 0,
                report.export_errors == 0,
                report.permission_errors == 0,
                report.raw_records == report.snapshots,
            )
        )
        return report

    def _verify_raw(self, report: VerificationReport) -> None:
        for path in (
            sorted(self.config.raw_dir.rglob("*.jsonl.gz")) if self.config.raw_dir.exists() else []
        ):
            try:
                with gzip.open(path, "rt", encoding="utf-8") as stream:
                    for line in stream:
                        json.loads(line)
                        report.raw_records += 1
            except (OSError, UnicodeError, json.JSONDecodeError):
                report.raw_errors += 1

    def _verify_blobs(self, report: VerificationReport) -> None:
        counts = dict(
            self.db.connection.execute(
                "SELECT status,count(*) FROM resources GROUP BY status"
            ).fetchall()
        )
        report.stored_resources = counts.get("stored", 0)
        report.failed_resources = counts.get("failed", 0)
        report.skipped_resources = counts.get("skipped", 0)
        report.pending_resources = counts.get("pending", 0)
        for row in self.db.connection.execute(
            "SELECT storage_path,sha256,byte_count FROM resources WHERE status='stored'"
        ):
            try:
                path = Path(row["storage_path"])
                digest = hashlib.sha256()
                size = 0
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        digest.update(chunk)
                        size += len(chunk)
                if digest.hexdigest() != row["sha256"] or size != row["byte_count"]:
                    report.bad_blobs += 1
            except OSError:
                report.bad_blobs += 1

    def _verify_exports(self, report: VerificationReport) -> None:
        for path in (
            sorted(self.config.exports_dir.glob("*.jsonl.gz"))
            if self.config.exports_dir.exists()
            else []
        ):
            try:
                with gzip.open(path, "rt", encoding="utf-8") as stream:
                    for line in stream:
                        json.loads(line)
                        report.export_records += 1
            except (OSError, UnicodeError, json.JSONDecodeError):
                report.export_errors += 1

    def _verify_online(self, report: VerificationReport) -> None:
        if self.discord is None:
            report.permission_errors += 1
            return
        total = 0
        for guild in self.discord.guilds():
            if self.config.guild_ids and str(guild["id"]) not in self.config.guild_ids:
                continue
            if hasattr(self.discord, "permission_errors"):
                self.discord.permission_errors.clear()
            for channel in self.discord.discover_targets(str(guild["id"])):
                total += sum(1 for _ in self.discord.iter_history(str(channel["id"])))
            report.permission_errors += len(getattr(self.discord, "permission_errors", []))
        report.online_messages = total
        report.online_delta = total - report.messages
