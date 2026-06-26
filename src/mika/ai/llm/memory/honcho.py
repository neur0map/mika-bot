"""Optional Honcho semantic memory (v3 REST API). Failures degrade to no-op."""

from __future__ import annotations

import re
from typing import Any

import httpx

from mika.core.config import get_settings
from mika.core.logging import get_logger

logger = get_logger(__name__)


def _sanitize(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value)


def _peer_id(discord_id: str) -> str:
    return f"discord_{_sanitize(discord_id)}"


class HonchoMemory:
    """Long-term, cross-session recall via a running Honcho stack."""

    def __init__(self) -> None:
        memory = get_settings().memory
        self._base = memory.honcho_base_url.rstrip("/")
        self._workspace = memory.honcho_workspace
        self._session = memory.honcho_session
        self._bot = _sanitize(get_settings().persona.name.lower()) or "bot"

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{self._base}{path}", json=payload)
                if response.is_error or response.status_code == httpx.codes.NO_CONTENT:
                    return None
                return response.json()
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("honcho request failed: %s", error)
            return None

    async def ensure(self) -> None:
        """Create the workspace, bot peer, and session if they do not exist."""
        await self._post("/v3/workspaces", {"id": self._workspace})
        await self._post(f"/v3/workspaces/{self._workspace}/peers", {"id": self._bot})
        await self._post(
            f"/v3/workspaces/{self._workspace}/sessions",
            {"id": self._session, "peers": {self._bot: {}}},
        )

    async def remember_user(self, *, discord_id: str, author_name: str, content: str) -> None:
        """Record a user's message under their own peer."""
        peer = _peer_id(discord_id)
        await self._post(
            f"/v3/workspaces/{self._workspace}/peers",
            {"id": peer, "metadata": {"displayName": author_name}},
        )
        await self._post(
            f"/v3/workspaces/{self._workspace}/sessions/{self._session}/peers", {peer: {}}
        )
        await self._post(
            f"/v3/workspaces/{self._workspace}/sessions/{self._session}/messages",
            {"messages": [{"peer_id": peer, "content": content}]},
        )

    async def remember_bot(self, content: str) -> None:
        """Record the bot's own reply."""
        await self._post(
            f"/v3/workspaces/{self._workspace}/sessions/{self._session}/messages",
            {"messages": [{"peer_id": self._bot, "content": content}]},
        )

    async def recall(self, query: str, limit: int = 6) -> str:
        """Return relevant past messages as a newline-joined context block."""
        if not query.strip():
            return ""
        data = await self._post(
            f"/v3/workspaces/{self._workspace}/search",
            {"query": query, "limit": limit},
        )
        if not isinstance(data, list):
            return ""
        lines = [
            f"{hit.get('peer_id', '?')}: {str(hit.get('content', ''))[:400]}"
            for hit in data
            if isinstance(hit, dict)
        ]
        return "\n".join(lines)
