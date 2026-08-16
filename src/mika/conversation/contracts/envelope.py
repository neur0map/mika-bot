"""Normalized current and referenced Discord conversation context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mika.conversation.contracts.media import MediaAsset


@dataclass(frozen=True, slots=True)
class ReferencedMessage:
    """A resolved reply target or forwarded message snapshot."""

    message_id: str
    author_id: str
    author_name: str
    text: str
    media: tuple[MediaAsset, ...] = ()


@dataclass(frozen=True, slots=True)
class ConversationEnvelope:
    """Everything one conversation turn knows before model processing."""

    message_id: str
    channel_id: str
    guild_id: str
    author_id: str
    author_name: str
    text: str
    mentioned: bool
    created_at: datetime
    media: tuple[MediaAsset, ...] = ()
    referenced: ReferencedMessage | None = None

    @property
    def visual_inputs(self) -> tuple[MediaAsset, ...]:
        """Return current then referenced media with stable URL deduplication."""
        candidates = self.media
        if self.referenced is not None:
            candidates += self.referenced.media
        seen: set[str] = set()
        unique: list[MediaAsset] = []
        for asset in candidates:
            if not asset.url or asset.url in seen:
                continue
            seen.add(asset.url)
            unique.append(asset)
        return tuple(unique)
