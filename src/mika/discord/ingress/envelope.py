"""Build platform-neutral conversation envelopes from Discord messages."""

from __future__ import annotations

from typing import cast

import discord
from mika.conversation.contracts.envelope import ConversationEnvelope, ReferencedMessage
from mika.discord.ingress.media import media_from_message


def _author_name(author: discord.abc.User) -> str:
    return str(getattr(author, "display_name", None) or author.name)


def _referenced_message(message: discord.Message) -> ReferencedMessage | None:
    reference = message.reference
    resolved = reference.resolved if reference is not None else None
    if resolved is None or not hasattr(resolved, "author"):
        return None
    target = cast(discord.Message, resolved)
    return ReferencedMessage(
        message_id=str(target.id),
        author_id=str(target.author.id),
        author_name=_author_name(target.author),
        text=target.content.strip(),
        media=media_from_message(target),
    )


def envelope_from_message(message: discord.Message, bot_user_id: int) -> ConversationEnvelope:
    """Normalize a Discord message and its resolved reply target."""
    guild_id = str(message.guild.id) if message.guild is not None else ""
    return ConversationEnvelope(
        message_id=str(message.id),
        channel_id=str(message.channel.id),
        guild_id=guild_id,
        author_id=str(message.author.id),
        author_name=_author_name(message.author),
        text=message.content.strip(),
        mentioned=any(user.id == bot_user_id for user in message.mentions),
        created_at=message.created_at,
        media=media_from_message(message),
        referenced=_referenced_message(message),
    )
