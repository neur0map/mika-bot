"""Normalized visual and playable media attached to a conversation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MediaKind = Literal["image", "gif", "video", "sticker", "clip", "unknown"]


@dataclass(frozen=True, slots=True)
class MediaAsset:
    """One canonical media resource with platform-neutral metadata."""

    kind: MediaKind
    url: str
    filename: str = ""
    content_type: str = ""
    source: str = "unknown"
    width: int | None = None
    height: int | None = None
