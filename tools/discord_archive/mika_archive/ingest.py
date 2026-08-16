from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from mika_archive.database import ArchiveDatabase, canonical_json
from mika_archive.raw_store import RawStore

_URL = re.compile(r"https?://[^\s<>\]\[\"']+", re.I)
_EMOJI = re.compile(r"<(a?):[A-Za-z0-9_]+:(\d+)>")


@dataclass(frozen=True, slots=True)
class IngestResult:
    messages_seen: int
    new_messages: int
    snapshots_added: int
    resources_linked: int


class MessageIngester:
    def __init__(self, database: ArchiveDatabase, raw_store: RawStore) -> None:
        self.db = database
        self.raw = raw_store

    def ingest_page(
        self,
        guild_id: str,
        channel: dict[str, Any],
        messages: Iterable[dict[str, Any]],
    ) -> IngestResult:
        batch = list(messages)
        new_messages = snapshots = links = 0
        self.db.upsert_channel({**channel, "guild_id": guild_id})
        with self.db.transaction() as con:
            for message in batch:
                message_id = str(message["id"])
                existed = (
                    con.execute("SELECT 1 FROM messages WHERE id=?", (message_id,)).fetchone()
                    is not None
                )
                raw_digest = hashlib.sha256((canonical_json(message) + "\n").encode()).hexdigest()
                seen_snapshot = (
                    con.execute(
                        "SELECT 1 FROM snapshots WHERE message_id=? AND raw_sha256=?",
                        (message_id, raw_digest),
                    ).fetchone()
                    is not None
                )
                self.db.upsert_message(guild_id, str(channel["id"]), message, commit=False)
                if not existed:
                    new_messages += 1
                if not seen_snapshot:
                    location = self.raw.append(guild_id, str(channel["id"]), message)
                    con.execute(
                        "INSERT INTO snapshots(message_id,raw_sha256,raw_path,raw_offset,recorded_at) VALUES(?,?,?,?,?)",
                        (message_id, location.sha256, str(location.path), location.offset, _now()),
                    )
                    snapshots += 1
                for resource in discover_resources(message):
                    con.execute(
                        "INSERT INTO resources(canonical_url,source_kind,status,discovered_at) VALUES(?,?,?,?) "
                        "ON CONFLICT(canonical_url) DO NOTHING",
                        (resource["url"], resource["kind"], "pending", _now()),
                    )
                    resource_id = con.execute(
                        "SELECT id FROM resources WHERE canonical_url=?", (resource["url"],)
                    ).fetchone()[0]
                    before = con.total_changes
                    con.execute(
                        "INSERT OR IGNORE INTO message_resources(message_id,resource_id,relation,original_name,declared_size,declared_mime) VALUES(?,?,?,?,?,?)",
                        (
                            message_id,
                            resource_id,
                            resource["relation"],
                            resource.get("name"),
                            resource.get("size"),
                            resource.get("mime"),
                        ),
                    )
                    links += int(con.total_changes > before)
            if batch:
                highest = str(max(int(item["id"]) for item in batch))
                existing = con.execute(
                    "SELECT highest_message_id FROM cursors WHERE channel_id=?",
                    (str(channel["id"]),),
                ).fetchone()
                if existing and existing[0]:
                    highest = str(max(int(existing[0]), int(highest)))
                con.execute(
                    "INSERT INTO cursors(channel_id,highest_message_id,last_success_at,last_error) VALUES(?,?,?,NULL) "
                    "ON CONFLICT(channel_id) DO UPDATE SET highest_message_id=excluded.highest_message_id,last_success_at=excluded.last_success_at,last_error=NULL",
                    (str(channel["id"]), highest, _now()),
                )
        return IngestResult(len(batch), new_messages, snapshots, links)


def discover_resources(message: dict[str, Any]) -> list[dict[str, Any]]:
    found: dict[tuple[str, str], dict[str, Any]] = {}

    def add(url: object, kind: str, relation: str, **extra: Any) -> None:
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            return
        cleaned = url.rstrip(".,;:!?)")
        found[(cleaned, relation)] = {"url": cleaned, "kind": kind, "relation": relation, **extra}

    for attachment in message.get("attachments", []):
        add(
            attachment.get("url"),
            "discord_attachment",
            "attachment",
            name=attachment.get("filename"),
            size=attachment.get("size"),
            mime=attachment.get("content_type"),
        )
    for sticker in message.get("sticker_items", []):
        fmt = int(sticker.get("format_type", 1))
        extension = {1: "png", 2: "png", 3: "json", 4: "gif"}.get(fmt, "png")
        add(
            f"https://cdn.discordapp.com/stickers/{sticker['id']}.{extension}",
            "discord_sticker",
            "sticker",
            name=sticker.get("name"),
        )
    for match in _URL.findall(str(message.get("content") or "")):
        add(match, "external_url", "content_url")
    for animated, emoji_id in _EMOJI.findall(str(message.get("content") or "")):
        extension = "gif" if animated else "png"
        add(
            f"https://cdn.discordapp.com/emojis/{emoji_id}.{extension}?size=4096&quality=lossless",
            "discord_emoji",
            "emoji",
        )
    for embed in message.get("embeds", []):
        _walk_embed(embed, add)
    return list(found.values())


def _walk_embed(value: Any, add: Any, key: str = "") -> None:
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key in {"url", "proxy_url"}:
                add(child, "embed_resource", f"embed_{child_key}")
            else:
                _walk_embed(child, add, child_key)
    elif isinstance(value, list):
        for child in value:
            _walk_embed(child, add, key)


def _now() -> str:
    return datetime.now(UTC).isoformat()
