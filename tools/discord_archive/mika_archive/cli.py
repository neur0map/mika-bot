from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from mika_archive.config import ArchiveConfig
from mika_archive.database import ArchiveDatabase
from mika_archive.discord import DiscordClient
from mika_archive.export import Exporter
from mika_archive.sync import ArchiveSynchronizer
from mika_archive.verify import Verifier


def main() -> int:
    parser = argparse.ArgumentParser(prog="archive")
    parser.add_argument("--dotenv", type=Path, default=Path("/opt/mikav2-bot/.env"))
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync")
    sync.add_argument("--full", action="store_true")
    sync.add_argument("--no-download", action="store_true")
    sync.add_argument("--no-reconcile", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("--online", action="store_true")
    sub.add_parser("export")
    download = sub.add_parser("download")
    download.add_argument("--workers", type=int, default=8)
    sub.add_parser("status")
    args = parser.parse_args()
    config = ArchiveConfig.from_dotenv(args.dotenv)
    os.umask(0o077)
    for path in (
        config.data_dir,
        config.raw_dir,
        config.media_dir,
        config.exports_dir,
        config.logs_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    db = ArchiveDatabase(config.database_path)
    db.initialize()
    discord = None
    try:
        if args.command == "sync":
            if not config.discord_token:
                parser.error("Discord token is not configured")
            discord = DiscordClient(config.discord_token)
            report = ArchiveSynchronizer(
                config,
                db,
                discord,
                progress=lambda event: print(json.dumps(event, sort_keys=True), flush=True),
            ).run(
                full=args.full,
                download_resources=not args.no_download,
                reconcile=not args.no_reconcile,
            )
            print(
                json.dumps(
                    report.__dict__
                    if hasattr(report, "__dict__")
                    else {name: getattr(report, name) for name in report.__dataclass_fields__},
                    sort_keys=True,
                )
            )
            return 0 if report.permission_errors == 0 else 2
        if args.command == "export":
            paths = Exporter(config, db).write()
            print(json.dumps({"messages": str(paths.messages), "resources": str(paths.resources)}))
            return 0
        if args.command == "download":
            report = ArchiveSynchronizer(
                config,
                db,
                None,
                progress=lambda event: print(json.dumps(event, sort_keys=True), flush=True),
            ).download_only(workers=max(1, args.workers))
            print(
                json.dumps(
                    {name: getattr(report, name) for name in report.__dataclass_fields__},
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "verify":
            if args.online:
                discord = DiscordClient(config.discord_token)
            report = Verifier(config, db, discord).run(online=args.online)
            config.logs_dir.mkdir(parents=True, exist_ok=True)
            output = (
                config.logs_dir
                / f"verification-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
            )
            output.write_text(
                json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print(json.dumps(report.to_dict(), sort_keys=True))
            return 0 if report.ok else 1
        counts = {
            table: db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("guilds", "channels", "messages", "snapshots", "resources", "runs")
        }
        counts["disk_bytes"] = sum(
            path.stat().st_size for path in config.data_dir.rglob("*") if path.is_file()
        )
        print(json.dumps(counts, sort_keys=True))
        return 0
    finally:
        if discord is not None:
            discord.close()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
