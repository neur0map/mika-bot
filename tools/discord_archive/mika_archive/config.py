from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ArchiveConfig:
    root: Path
    discord_token: str
    guild_ids: tuple[str, ...]
    max_resource_bytes: int = 512 * 1024 * 1024
    reconcile_messages: int = 100

    @classmethod
    def for_root(
        cls,
        root: Path,
        *,
        discord_token: str = "",
        guild_ids: tuple[str, ...] = (),
    ) -> ArchiveConfig:
        return cls(root.resolve(), discord_token, guild_ids)

    @classmethod
    def from_environment(cls) -> ArchiveConfig:
        root = Path(os.environ.get("MIKA_ARCHIVE_ROOT", "/srv/mika-discord-archive"))
        token = os.environ.get("DISCORD_TOKEN", "")
        guild_ids = tuple(
            x.strip() for x in os.environ.get("DISCORD_GUILD_IDS", "").split(",") if x.strip()
        )
        return cls.for_root(root, discord_token=token, guild_ids=guild_ids)

    @classmethod
    def from_dotenv(cls, path: Path = Path("/opt/mikav2-bot/.env")) -> ArchiveConfig:
        values: dict[str, str] = {}
        if path.exists():
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, raw_value = line.split("=", 1)
                try:
                    parts = shlex.split(raw_value, comments=True)
                    values[key.strip()] = parts[0] if parts else ""
                except ValueError:
                    values[key.strip()] = raw_value.strip().strip("'\"")
        token = os.environ.get("DISCORD_TOKEN", values.get("DISCORD_TOKEN", ""))
        guild_text = os.environ.get("DISCORD_GUILD_IDS", values.get("DISCORD_GUILD_IDS", ""))
        guild_ids = tuple(x.strip() for x in guild_text.split(",") if x.strip())
        root = Path(os.environ.get("MIKA_ARCHIVE_ROOT", "/srv/mika-discord-archive"))
        return cls.for_root(root, discord_token=token, guild_ids=guild_ids)

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "archive.sqlite3"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media" / "sha256"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"
