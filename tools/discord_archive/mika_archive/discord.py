from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx


class DiscordAPIError(RuntimeError):
    pass


class DiscordClient:
    API = "https://discord.com/api/v10"
    HISTORY_TYPES = frozenset({0, 5, 10, 11, 12})
    THREAD_PARENT_TYPES = frozenset({0, 5, 15, 16})

    def __init__(
        self,
        token: str,
        *,
        transport: httpx.BaseTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        timeout: float = 30,
    ) -> None:
        self._token = token
        self._sleep = sleeper
        self._client = httpx.Client(
            base_url=self.API,
            headers={"Authorization": f"Bot {token}", "User-Agent": "MikaLocalArchive/1.0"},
            transport=transport,
            timeout=timeout,
            follow_redirects=False,
        )
        self.permission_errors: list[dict[str, Any]] = []

    def close(self) -> None:
        self._client.close()

    def request_json(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        transient_attempts = 0
        while True:
            try:
                response = self._client.request(method, path, params=params)
            except httpx.HTTPError as error:
                transient_attempts += 1
                if transient_attempts > 4:
                    raise DiscordAPIError(
                        f"Discord request failed: {type(error).__name__}"
                    ) from error
                self._sleep(min(2**transient_attempts, 10))
                continue
            if response.status_code == 429:
                retry = float(response.json().get("retry_after", 1))
                self._sleep(max(0, retry) + 0.05)
                continue
            if response.status_code >= 500 and transient_attempts < 4:
                transient_attempts += 1
                self._sleep(min(2**transient_attempts, 10))
                continue
            if response.is_error:
                raise DiscordAPIError(f"Discord API {response.status_code} for {path}")
            return response.json()

    def guilds(self) -> list[dict[str, Any]]:
        value = self.request_json("GET", "/users/@me/guilds")
        return list(value)

    def discover_targets(self, guild_id: str) -> list[dict[str, Any]]:
        channels = list(self.request_json("GET", f"/guilds/{guild_id}/channels"))
        by_id: dict[str, dict[str, Any]] = {
            str(item["id"]): item
            for item in channels
            if int(item.get("type", -1)) in self.HISTORY_TYPES
        }
        active = self.request_json("GET", f"/guilds/{guild_id}/threads/active")
        for thread in active.get("threads", []):
            by_id[str(thread["id"])] = thread
        for parent in channels:
            if int(parent.get("type", -1)) not in self.THREAD_PARENT_TYPES:
                continue
            for visibility in ("public", "private"):
                before: str | None = None
                while True:
                    params: dict[str, Any] = {"limit": 100}
                    if before:
                        params["before"] = before
                    path = f"/channels/{parent['id']}/threads/archived/{visibility}"
                    try:
                        payload = self.request_json("GET", path, params)
                    except DiscordAPIError as error:
                        self.permission_errors.append(
                            {
                                "channel_id": str(parent["id"]),
                                "scope": visibility,
                                "error": str(error),
                            }
                        )
                        break
                    batch = list(payload.get("threads", []))
                    for thread in batch:
                        by_id[str(thread["id"])] = thread
                    if not payload.get("has_more") or not batch:
                        break
                    before = batch[-1].get("thread_metadata", {}).get("archive_timestamp")
                    if not before:
                        break
        return sorted(
            by_id.values(), key=lambda item: (int(item.get("position", 0)), int(item["id"]))
        )

    def iter_history(
        self,
        channel_id: str,
        *,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        yielded = 0
        cursor_after = after
        cursor_before = before
        while limit is None or yielded < limit:
            page_limit = min(100, limit - yielded) if limit is not None else 100
            params: dict[str, Any] = {"limit": page_limit}
            if cursor_after:
                params["after"] = cursor_after
            elif cursor_before:
                params["before"] = cursor_before
            batch = list(self.request_json("GET", f"/channels/{channel_id}/messages", params))
            if not batch:
                return
            ordered = sorted(batch, key=lambda item: int(item["id"]))
            for message in ordered:
                yield message
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            if len(batch) < page_limit:
                return
            if cursor_after is not None:
                cursor_after = max(batch, key=lambda item: int(item["id"]))["id"]
            else:
                cursor_before = min(batch, key=lambda item: int(item["id"]))["id"]
