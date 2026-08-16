"""Normalize Discord attachments, embeds, and stickers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

import discord
from mika.conversation.contracts.media import MediaAsset, MediaKind

_GIF_SUFFIXES = (".gif",)
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
_VIDEO_SUFFIXES = (".mp4", ".webm", ".mov")
_MAX_MEDIA = 4


def _without_query(url: str) -> str:
    return url.split("?", 1)[0].lower()


def _kind(url: str, content_type: str, *, embed_type: str = "") -> MediaKind:
    clean_url = _without_query(url)
    clean_type = content_type.lower()
    if clean_type == "image/gif" or clean_url.endswith(_GIF_SUFFIXES) or embed_type == "gifv":
        return "gif"
    if clean_type.startswith("image/") or clean_url.endswith(_IMAGE_SUFFIXES):
        return "image"
    if clean_type.startswith("video/") or clean_url.endswith(_VIDEO_SUFFIXES):
        return "video"
    return "unknown"


def _deduplicate(assets: Iterable[MediaAsset]) -> tuple[MediaAsset, ...]:
    seen: set[str] = set()
    result: list[MediaAsset] = []
    for asset in assets:
        if not asset.url or asset.url in seen or asset.kind == "unknown":
            continue
        seen.add(asset.url)
        result.append(asset)
        if len(result) == _MAX_MEDIA:
            break
    return tuple(result)


def _embed_asset(embed: discord.Embed) -> MediaAsset | None:
    target = embed.video or embed.image or embed.thumbnail
    url = str(target.url or "") if target else ""
    if not url:
        return None
    kind = _kind(url, "", embed_type=str(embed.type or "").lower())
    return MediaAsset(
        kind=kind,
        url=url,
        filename=str(embed.title or embed.url or ""),
        source="embed",
        width=cast(int | None, getattr(target, "width", None)),
        height=cast(int | None, getattr(target, "height", None)),
    )


def media_from_message(message: discord.Message) -> tuple[MediaAsset, ...]:
    """Return bounded visual media carried by one Discord message."""
    assets: list[MediaAsset] = []
    for attachment in message.attachments:
        content_type = attachment.content_type or ""
        assets.append(
            MediaAsset(
                kind=_kind(attachment.url, content_type),
                url=attachment.url,
                filename=attachment.filename,
                content_type=content_type,
                source="attachment",
                width=attachment.width,
                height=attachment.height,
            )
        )
    for embed in message.embeds:
        asset = _embed_asset(embed)
        if asset is not None:
            assets.append(asset)
    for sticker in message.stickers:
        assets.append(
            MediaAsset(
                kind="sticker",
                url=str(sticker.url),
                filename=sticker.name,
                source="sticker",
            )
        )
    return _deduplicate(assets)
