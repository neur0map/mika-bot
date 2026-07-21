"""Discord application-command cleanup safety tests."""

from __future__ import annotations

import httpx
import pytest

from mika.cli.commands.cleanup_commands import DiscordCommandCleaner


@pytest.mark.asyncio
async def test_cleanup_enumerates_then_bulk_overwrites_global_and_guild_commands() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": "not-recorded"}])
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://discord.test/api/v10", transport=transport
    ) as client:
        cleaner = DiscordCommandCleaner("123", "token-value", ("456",), client)
        result = await cleaner.cleanup()

    assert result.global_count == 1
    assert result.guild_counts == {"456": 1}
    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/api/v10/applications/123/commands"),
        ("GET", "/api/v10/applications/123/guilds/456/commands"),
        ("PUT", "/api/v10/applications/123/commands"),
        ("PUT", "/api/v10/applications/123/guilds/456/commands"),
    ]
    assert all(request.content == b"[]" for request in requests if request.method == "PUT")
    assert all(request.headers["Authorization"] == "Bot token-value" for request in requests)


@pytest.mark.asyncio
async def test_cleanup_does_not_overwrite_when_enumeration_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "forbidden"})

    async with httpx.AsyncClient(
        base_url="https://discord.test/api/v10", transport=httpx.MockTransport(handler)
    ) as client:
        cleaner = DiscordCommandCleaner("123", "token-value", (), client)
        with pytest.raises(httpx.HTTPStatusError):
            await cleaner.cleanup()
