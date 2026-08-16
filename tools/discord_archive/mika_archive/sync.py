from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mika_archive.config import ArchiveConfig
from mika_archive.database import ArchiveDatabase
from mika_archive.ingest import MessageIngester
from mika_archive.raw_store import RawStore
from mika_archive.resources import ResourceDownloader, extract_media_targets


@dataclass(slots=True)
class SyncReport:
    mode: str
    guilds: int = 0
    targets: int = 0
    messages_seen: int = 0
    new_messages: int = 0
    snapshots_added: int = 0
    resources_linked: int = 0
    resources_stored: int = 0
    resources_failed: int = 0
    resources_skipped: int = 0
    permission_errors: int = 0


class ArchiveSynchronizer:
    def __init__(
        self,
        config: ArchiveConfig,
        database: ArchiveDatabase,
        discord: Any,
        progress: Callable[[dict[str, Any]], None] | None = None,
        downloader_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.config = config
        self.db = database
        self.discord = discord
        self.ingester = MessageIngester(database, RawStore(config.raw_dir))
        self.progress = progress or (lambda event: None)
        self.downloader_factory = downloader_factory or (
            lambda: ResourceDownloader(
                self.config.media_dir, max_bytes=self.config.max_resource_bytes
            )
        )

    def run(
        self,
        *,
        full: bool = False,
        download_resources: bool = True,
        reconcile: bool = True,
    ) -> SyncReport:
        mode = "full" if full else "incremental"
        report = SyncReport(mode)
        run_id = self._start_run(mode)
        try:
            guilds = self.discord.guilds()
            if self.config.guild_ids:
                guilds = [g for g in guilds if str(g["id"]) in self.config.guild_ids]
            report.guilds = len(guilds)
            for guild in guilds:
                guild_id = str(guild["id"])
                self.db.upsert_guild(guild)
                if hasattr(self.discord, "permission_errors"):
                    self.discord.permission_errors.clear()
                targets = self.discord.discover_targets(guild_id)
                report.targets += len(targets)
                for target_index, channel in enumerate(targets, 1):
                    self.db.upsert_channel({**channel, "guild_id": guild_id})
                    cursor = None if full else self._cursor(str(channel["id"]))
                    for page in _pages(
                        self.discord.iter_history(str(channel["id"]), after=cursor), 100
                    ):
                        result = self.ingester.ingest_page(guild_id, channel, page)
                        report.messages_seen += result.messages_seen
                        report.new_messages += result.new_messages
                        report.snapshots_added += result.snapshots_added
                        report.resources_linked += result.resources_linked
                    if reconcile and not full:
                        recent = list(
                            self.discord.iter_history(
                                str(channel["id"]), limit=self.config.reconcile_messages
                            )
                        )
                        if recent:
                            result = self.ingester.ingest_page(guild_id, channel, recent)
                            report.messages_seen += result.messages_seen
                            report.new_messages += result.new_messages
                            report.snapshots_added += result.snapshots_added
                            report.resources_linked += result.resources_linked
                    self.progress(
                        {
                            "event": "channel",
                            "index": target_index,
                            "of": len(targets),
                            "channel_id": str(channel["id"]),
                            "name": channel.get("name", ""),
                            "messages_seen": report.messages_seen,
                            "new_messages": report.new_messages,
                        }
                    )
                report.permission_errors += len(getattr(self.discord, "permission_errors", []))
            if download_resources:
                self._download_resources(report)
            status = "complete" if report.permission_errors == 0 else "partial"
            self._finish_run(run_id, status, report)
            return report
        except Exception:
            self._finish_run(run_id, "failed", report)
            raise

    def _cursor(self, channel_id: str) -> str | None:
        row = self.db.connection.execute(
            "SELECT highest_message_id FROM cursors WHERE channel_id=?", (channel_id,)
        ).fetchone()
        return str(row[0]) if row and row[0] else None

    def download_only(self, *, workers: int = 8) -> SyncReport:
        report = SyncReport("resources")
        self._download_resources(report, workers=workers)
        return report

    def _download_resources(self, report: SyncReport, *, workers: int = 8) -> None:
        self._discover_discord_fallbacks()
        self._download_pass(report, include_failed=True, workers=workers)
        self._discover_html_media()
        self._download_pass(report, include_failed=False, workers=workers)

    def _discover_discord_fallbacks(self) -> None:
        rows = self.db.connection.execute(
            "SELECT id,canonical_url,source_kind FROM resources WHERE status='failed' AND source_kind IN ('discord_sticker','discord_emoji')"
        ).fetchall()
        for row in rows:
            identifier = row["canonical_url"].rsplit("/", 1)[-1].split(".", 1)[0].split("?", 1)[0]
            if not identifier.isdigit():
                continue
            if row["source_kind"] == "discord_sticker":
                target = f"https://media.discordapp.net/stickers/{identifier}.gif?size=1024"
                kind = "discord_sticker_fallback"
            else:
                target = f"https://cdn.discordapp.com/emojis/{identifier}.webp?size=1024"
                kind = "discord_emoji_fallback"
            with self.db.transaction() as con:
                con.execute(
                    "INSERT INTO resources(canonical_url,source_kind,status,discovered_at) VALUES(?,?, 'pending', ?) ON CONFLICT(canonical_url) DO NOTHING",
                    (target, kind, _now()),
                )
                fallback_id = con.execute(
                    "SELECT id FROM resources WHERE canonical_url=?", (target,)
                ).fetchone()[0]
                for message in con.execute(
                    "SELECT message_id FROM message_resources WHERE resource_id=?", (row["id"],)
                ).fetchall():
                    con.execute(
                        "INSERT OR IGNORE INTO message_resources(message_id,resource_id,relation) VALUES(?,?,'discord_fallback')",
                        (message[0], fallback_id),
                    )

    def _download_pass(self, report: SyncReport, *, include_failed: bool, workers: int) -> None:
        statuses = "('pending','failed')" if include_failed else "('pending')"
        rows = self.db.connection.execute(
            f"SELECT id,canonical_url,source_kind FROM resources WHERE status IN {statuses} ORDER BY id"
        ).fetchall()
        total = len(rows)
        completed = 0
        batches = list(_chunks(rows, 16))
        with ThreadPoolExecutor(
            max_workers=max(1, workers), thread_name_prefix="archive-download"
        ) as pool:
            futures = [pool.submit(self._download_batch, batch) for batch in batches]
            for future in as_completed(futures):
                for row, result in future.result():
                    with self.db.transaction() as con:
                        con.execute(
                            "UPDATE resources SET status=?,http_status=?,final_url=?,mime_type=?,byte_count=?,sha256=?,storage_path=?,error=?,attempts=attempts+1,attempted_at=?,stored_at=? WHERE id=?",
                            (
                                result.status,
                                result.http_status,
                                result.final_url,
                                result.mime_type,
                                result.byte_count,
                                result.sha256,
                                str(result.path) if result.path else None,
                                result.error,
                                _now(),
                                _now() if result.status == "stored" else None,
                                row["id"],
                            ),
                        )
                    if result.status == "stored":
                        report.resources_stored += 1
                    elif result.status == "failed":
                        report.resources_failed += 1
                    else:
                        report.resources_skipped += 1
                    completed += 1
                self.progress(
                    {
                        "event": "resources",
                        "index": completed,
                        "of": total,
                        "stored": report.resources_stored,
                        "failed": report.resources_failed,
                        "skipped": report.resources_skipped,
                    }
                )

    def _download_batch(self, rows: list[Any]) -> list[tuple[Any, Any]]:
        downloader = self.downloader_factory()
        try:
            return [(row, downloader.download(row["canonical_url"])) for row in rows]
        finally:
            downloader.close()

    def _discover_html_media(self) -> None:
        rows = self.db.connection.execute(
            "SELECT id,final_url,storage_path FROM resources WHERE status='stored' AND source_kind IN ('external_url','embed_resource') AND mime_type IN ('text/html','application/xhtml+xml')"
        ).fetchall()
        for row in rows:
            path = Path(row["storage_path"])
            if not path.exists() or path.stat().st_size > 16 * 1024 * 1024:
                continue
            html = path.read_text(encoding="utf-8", errors="replace")
            for target in extract_media_targets(html, row["final_url"]):
                with self.db.transaction() as con:
                    con.execute(
                        "INSERT INTO resources(canonical_url,source_kind,status,discovered_at) VALUES(?,'derived_media','pending',?) ON CONFLICT(canonical_url) DO NOTHING",
                        (target, _now()),
                    )
                    derived_id = con.execute(
                        "SELECT id FROM resources WHERE canonical_url=?", (target,)
                    ).fetchone()[0]
                    messages = con.execute(
                        "SELECT message_id FROM message_resources WHERE resource_id=?", (row["id"],)
                    ).fetchall()
                    for message in messages:
                        con.execute(
                            "INSERT OR IGNORE INTO message_resources(message_id,resource_id,relation) VALUES(?,?,'derived_media')",
                            (message[0], derived_id),
                        )

    def _start_run(self, mode: str) -> int:
        cursor = self.db.connection.execute(
            "INSERT INTO runs(mode,started_at,status) VALUES(?,?,'running')", (mode, _now())
        )
        self.db.connection.commit()
        return int(cursor.lastrowid)

    def _finish_run(self, run_id: int, status: str, report: SyncReport) -> None:
        self.db.connection.execute(
            "UPDATE runs SET finished_at=?,status=?,report_json=? WHERE id=?",
            (_now(), status, json.dumps(asdict(report), sort_keys=True), run_id),
        )
        self.db.connection.commit()


def _pages(items: Iterable[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    page: list[dict[str, Any]] = []
    for item in items:
        page.append(item)
        if len(page) == size:
            yield page
            page = []
    if page:
        yield page


def _chunks(items: list[Any], size: int) -> Iterator[list[Any]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _now() -> str:
    return datetime.now(UTC).isoformat()
