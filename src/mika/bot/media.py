"""Klipy media search usable by chat replies and commands."""

from __future__ import annotations

import re
import secrets
from typing import Any

import httpx

from mika.core.config import get_settings

_MEDIA_SUFFIXES = (".gif", ".gifv", ".mp4", ".webp", ".webm")
_MAX_QUERY_WORDS = 6
_MAX_QUERY_CHARS = 70


def normalize_media_query(query: str) -> str:
    """Turn a model media query into a short searchable mood/action phrase."""
    cleaned = re.sub(r"https?://\S+", " ", query.lower())
    cleaned = re.sub(r"[^a-z0-9\s'-]+", " ", cleaned)
    words = [word for word in cleaned.split() if len(word) > 1]
    return " ".join(words[:_MAX_QUERY_WORDS])[:_MAX_QUERY_CHARS].strip()


def first_media_url(obj: Any) -> str | None:
    """Return the first playable media URL found in a nested API payload."""
    if isinstance(obj, str):
        low = obj.lower()
        return obj if obj.startswith("http") and low.endswith(_MEDIA_SUFFIXES) else None
    if isinstance(obj, dict):
        for value in obj.values():
            found = first_media_url(value)
            if found:
                return found
    if isinstance(obj, list):
        for value in obj:
            found = first_media_url(value)
            if found:
                return found
    return None


async def search_klipy(kind: str, query: str) -> str | None:
    """Search Klipy for one playable GIF/sticker/clip URL."""
    key = get_settings().media.klipy_api_key
    normalized_query = normalize_media_query(query)
    if not key or not normalized_query:
        return None
    normalized = kind if kind in {"gifs", "stickers", "clips"} else "gifs"
    url = f"https://api.klipy.com/api/v1/{key}/{normalized}/search"
    async with httpx.AsyncClient(timeout=6.0) as client:
        response = await client.get(url, params={"q": normalized_query, "per_page": 24})
        response.raise_for_status()
    data = response.json()
    results = data.get("data", {}).get("data") or data.get("data") or []
    results = results if isinstance(results, list) else []
    if not results:
        return None
    return first_media_url(secrets.choice(results)) or first_media_url(results)
