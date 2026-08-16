from __future__ import annotations

import unittest

import httpx
from mika_archive.discord import DiscordClient


def response(status: int, data: object, request: httpx.Request) -> httpx.Response:
    return httpx.Response(status, json=data, request=request)


class DiscordClientTests(unittest.TestCase):
    def test_retries_rate_limit_without_exposing_token(self) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return (
                response(429, {"retry_after": 0}, request)
                if calls == 1
                else response(200, {"ok": True}, request)
            )

        client = DiscordClient(
            "secret-token", transport=httpx.MockTransport(handler), sleeper=lambda _: None
        )
        self.assertEqual(client.request_json("GET", "/ok"), {"ok": True})
        self.assertEqual(calls, 2)

    def test_discovers_base_active_and_archived_threads(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("/channels"):
                return response(
                    200,
                    [
                        {"id": "10", "guild_id": "1", "name": "general", "type": 0},
                        {"id": "20", "guild_id": "1", "name": "forum", "type": 15},
                    ],
                    request,
                )
            if path.endswith("/threads/active"):
                return response(
                    200,
                    {
                        "threads": [
                            {
                                "id": "30",
                                "guild_id": "1",
                                "parent_id": "20",
                                "name": "active",
                                "type": 11,
                            }
                        ]
                    },
                    request,
                )
            if path.endswith("/threads/archived/public"):
                return response(
                    200,
                    {
                        "threads": [
                            {
                                "id": "40",
                                "guild_id": "1",
                                "parent_id": "20",
                                "name": "old",
                                "type": 11,
                            }
                        ],
                        "has_more": False,
                    },
                    request,
                )
            if path.endswith("/threads/archived/private"):
                return response(200, {"threads": [], "has_more": False}, request)
            raise AssertionError(path)

        client = DiscordClient("x", transport=httpx.MockTransport(handler))
        targets = client.discover_targets("1")
        self.assertEqual({x["id"] for x in targets}, {"10", "30", "40"})
        self.assertEqual(client.permission_errors, [])

    def test_history_full_pages_oldest_first_and_after_cursor(self) -> None:
        seen_after: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            after = request.url.params.get("after")
            seen_after.append(after)
            if len(seen_after) == 1:
                batch = [{"id": str(x)} for x in range(200, 100, -1)]
            else:
                batch = [{"id": "201"}]
            return response(200, batch, request)

        client = DiscordClient("x", transport=httpx.MockTransport(handler))
        messages = list(client.iter_history("9", after="100"))
        self.assertEqual(messages[0]["id"], "101")
        self.assertEqual(messages[-1]["id"], "201")
        self.assertEqual(seen_after, ["100", "200"])


if __name__ == "__main__":
    unittest.main()
