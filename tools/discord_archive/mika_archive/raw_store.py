from __future__ import annotations

import gzip
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from mika_archive.database import canonical_json


@dataclass(frozen=True, slots=True)
class SnapshotLocation:
    path: Path
    offset: int
    sha256: str


class RawStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def append(self, guild_id: str, channel_id: str, message: dict[str, Any]) -> SnapshotLocation:
        timestamp = datetime.fromisoformat(str(message["timestamp"]).replace("Z", "+00:00"))
        path = (
            self.root
            / guild_id
            / channel_id
            / f"{timestamp.year:04d}"
            / f"{timestamp.month:02d}.jsonl.gz"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (canonical_json(message) + "\n").encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        with path.open("ab") as raw:
            offset = raw.tell()
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as zipped:
                zipped.write(payload)
            raw.flush()
            os.fsync(raw.fileno())
        return SnapshotLocation(path.resolve(), offset, digest)
