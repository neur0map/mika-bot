"""Operator-only removal of stale Discord application commands."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

import httpx
import typer
from rich.console import Console

from mika.core.config import get_settings
from mika.persistence.shared_archive import archive_event

console = Console()
_CONFIRMATION = "delete-discord-commands"
_API_BASE = "https://discord.com/api/v10"


@dataclass(frozen=True)
class CleanupResult:
    """Counts of application commands removed from Discord scopes."""

    global_count: int
    guild_counts: dict[str, int]

    @property
    def total(self) -> int:
        """Return the total number of removed commands."""
        return self.global_count + sum(self.guild_counts.values())


class DiscordCommandCleaner:
    """Use Discord's documented bulk-overwrite endpoints with an empty command list."""

    def __init__(
        self,
        application_id: str,
        token: str,
        guild_ids: Sequence[str],
        client: httpx.AsyncClient,
    ) -> None:
        self._application_id = application_id
        self._guild_ids = tuple(guild_ids)
        self._client = client
        self._headers = {"Authorization": f"Bot {token}"}

    def _path(self, guild_id: str | None = None) -> str:
        root = f"/applications/{self._application_id}"
        return f"{root}/guilds/{guild_id}/commands" if guild_id else f"{root}/commands"

    async def _list_count(self, guild_id: str | None = None) -> int:
        response = await self._client.get(self._path(guild_id), headers=self._headers)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Discord command list was not an array")
        return len(payload)

    async def _clear(self, guild_id: str | None = None) -> None:
        response = await self._client.put(self._path(guild_id), headers=self._headers, json=[])
        response.raise_for_status()

    async def cleanup(self) -> CleanupResult:
        """Enumerate every configured scope before clearing any of them."""
        global_count = await self._list_count()
        guild_counts = {guild_id: await self._list_count(guild_id) for guild_id in self._guild_ids}
        await self._clear()
        for guild_id in self._guild_ids:
            await self._clear(guild_id)
        return CleanupResult(global_count=global_count, guild_counts=guild_counts)


async def _record_cleanup(result: CleanupResult) -> None:
    await archive_event(
        {
            "event_type": "discord_command_cleanup",
            "created_at": datetime.now(tz=UTC).isoformat(),
            "payload": {
                "globalCount": result.global_count,
                "guildCounts": result.guild_counts,
                "totalCount": result.total,
            },
        }
    )


async def _cleanup_configured_commands() -> CleanupResult:
    settings = get_settings()
    if not settings.discord.client_id or not settings.discord.token:
        raise typer.BadParameter("DISCORD_CLIENT_ID and DISCORD_TOKEN must be configured")
    async with httpx.AsyncClient(base_url=_API_BASE, timeout=15.0) as client:
        cleaner = DiscordCommandCleaner(
            settings.discord.client_id,
            settings.discord.token,
            settings.discord.guild_id_list,
            client,
        )
        result = await cleaner.cleanup()
    await _record_cleanup(result)
    return result


def cleanup_commands(
    confirm: Annotated[
        str | None,
        typer.Option(help=f"Required exact acknowledgement: {_CONFIRMATION}"),
    ] = None,
) -> None:
    """Permanently delete stale global and configured-guild application commands."""
    if confirm != _CONFIRMATION:
        console.print(f"[red]Refusing cleanup. Pass --confirm {_CONFIRMATION} to continue.[/]")
        raise typer.Exit(2)
    try:
        result = asyncio.run(_cleanup_configured_commands())
    except (httpx.HTTPError, ValueError, typer.BadParameter) as error:
        console.print(f"[red]Command cleanup failed: {error}[/]")
        raise typer.Exit(1) from error
    console.print(
        "[green]Deleted stale Discord application commands:[/] "
        f"{result.global_count} global, {sum(result.guild_counts.values())} guild, "
        f"{result.total} total."
    )
