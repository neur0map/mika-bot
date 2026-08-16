"""Discord execution reports only actions that became visible."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import discord

from mika.conversation.actions import ActionPlan, MediaRequest
from mika.discord.execution import DiscordActionExecutor


class Channel:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, text: str) -> None:
        self.sent.append(text)


class Message:
    def __init__(self, *, reaction_fails: bool = False) -> None:
        self.channel = Channel()
        self.reaction_fails = reaction_fails
        self.replies: list[str] = []
        self.reactions: list[str] = []

    async def add_reaction(self, emoji: str) -> None:
        if self.reaction_fails:
            raise discord.HTTPException(SimpleNamespace(status=400, reason="bad"), "bad")
        self.reactions.append(emoji)

    async def reply(self, text: str) -> Any:
        self.replies.append(text)
        return SimpleNamespace(id=42)


async def media_search(kind: str, query: str) -> str | None:
    return f"https://cdn.example/{kind}/{query}.gif"


async def test_executor_reports_partial_failure_and_successful_media() -> None:
    message = Message(reaction_fails=True)
    plan = ActionPlan(
        reply="we did it",
        reactions=("🔥",),
        media=MediaRequest("gif", "victory dance"),
    )

    result = await DiscordActionExecutor(media_search).execute(cast(discord.Message, message), plan)

    assert result.reply_message_id == "42"
    assert result.applied_reactions == ()
    assert result.media_url == "https://cdn.example/gif/victory dance.gif"
    assert result.failures == ("reaction:HTTPException",)
    assert message.channel.sent == ["https://cdn.example/gif/victory dance.gif"]


async def test_executor_can_send_media_without_text() -> None:
    message = Message()
    plan = ActionPlan(media=MediaRequest("gif", "side eye"))

    result = await DiscordActionExecutor(media_search).execute(cast(discord.Message, message), plan)

    assert result.reply_message_id is None
    assert result.media_url is not None
    assert message.replies == []
