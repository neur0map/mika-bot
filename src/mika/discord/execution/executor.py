"""Execute text, reaction, and media plans through the Discord Bot API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import discord

from mika.conversation.actions import ActionPlan, ExecutionResult

MediaSearch = Callable[[str, str], Awaitable[str | None]]
_MAX_REPLY = 1990


class DiscordActionExecutor:
    """Attempt independent Discord actions and report only visible successes."""

    def __init__(self, media_search: MediaSearch) -> None:
        self._media_search = media_search

    async def execute(self, message: discord.Message, plan: ActionPlan) -> ExecutionResult:
        """Execute a plan without letting one optional action cancel the others."""
        failures: list[str] = []
        reactions: list[str] = []
        for emoji in plan.reactions:
            try:
                await message.add_reaction(emoji)
                reactions.append(emoji)
            except Exception as error:
                failures.append(f"reaction:{type(error).__name__}")

        reply_id: str | None = None
        if plan.reply.strip():
            try:
                sent = await message.reply(plan.reply[:_MAX_REPLY])
                reply_id = str(sent.id)
            except Exception as error:
                failures.append(f"reply:{type(error).__name__}")

        media_url: str | None = None
        if plan.media is not None:
            try:
                candidate = await self._media_search(plan.media.kind, plan.media.query)
                if candidate:
                    await message.channel.send(candidate)
                    media_url = candidate
                else:
                    failures.append("media:not_found")
            except Exception as error:
                failures.append(f"media:{type(error).__name__}")

        return ExecutionResult(reply_id, tuple(reactions), media_url, tuple(failures))
