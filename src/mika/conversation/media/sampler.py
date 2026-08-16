"""Fetch animated media safely and prepare bounded vision inputs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx

from mika.conversation.contracts import MediaAsset
from mika.conversation.media.frames import sample_animated_frames

MediaFetch = Callable[[str], Awaitable[tuple[bytes, str]]]
_MAX_SOURCE_BYTES = 8 * 1024 * 1024
_MAX_VISION_INPUTS = 4
_HEADERS = {"User-Agent": "MikaBot/0.2 media-context"}


def media_context(assets: tuple[MediaAsset, ...]) -> str:
    """Describe visual inputs as social evidence without pretending to see them."""
    if not assets:
        return ""
    lines = [
        f"- {asset.kind}, {asset.source}"
        + (f", {asset.content_type}" if asset.content_type else "")
        + (f": {asset.filename[:120]}" if asset.filename else "")
        for asset in assets[:4]
    ]
    temporal = (
        " Animated media is attached as chronological sampled frames."
        if any(_looks_animated(asset) for asset in assets)
        else ""
    )
    return (
        "[incoming media context: look at the attached media and treat it as a social cue;"
        f"{temporal} Do not narrate it unless asked.]\n" + "\n".join(lines)
    )


class TemporalMediaSampler:
    """Expand animated assets into chronological frames without delaying static images."""

    def __init__(self, fetch: MediaFetch | None = None, *, max_frames: int = 3) -> None:
        self._fetch = fetch or _fetch_media
        self._max_frames = max(2, min(max_frames, _MAX_VISION_INPUTS))

    async def prepare(self, assets: tuple[MediaAsset, ...]) -> tuple[str, ...]:
        """Return at most four provider-ready URLs or sampled data URLs."""
        prepared: list[str] = []
        for asset in assets:
            if len(prepared) >= _MAX_VISION_INPUTS:
                break
            if not _looks_animated(asset):
                prepared.append(asset.url)
                continue
            try:
                data, content_type = await self._fetch(asset.url)
            except Exception:
                prepared.append(asset.url)
                continue
            if len(data) > _MAX_SOURCE_BYTES or content_type not in {"image/gif", "image/webp"}:
                prepared.append(asset.url)
                continue
            remaining = _MAX_VISION_INPUTS - len(prepared)
            frames = sample_animated_frames(data, max_frames=min(self._max_frames, remaining))
            prepared.extend(frames or (asset.url,))
        return tuple(prepared)


def _looks_animated(asset: MediaAsset) -> bool:
    path = asset.url.partition("?")[0].casefold()
    return asset.content_type.casefold() in {"image/gif", "image/webp"} or path.endswith(
        (".gif", ".webp")
    )


async def _fetch_media(url: str) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=6.0, follow_redirects=True, headers=_HEADERS) as client:
        response = await client.get(url)
        response.raise_for_status()
    content_type = (response.headers.get("content-type") or "").partition(";")[0].strip()
    return response.content, content_type
