"""on_message: route mentions and free-chat channels to the AI brain."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import discord

from mika.bot.media import search_klipy
from mika.core.config import get_settings
from mika.core.logging import get_logger
from mika.persistence.shared_archive import archive_event, archive_message

if TYPE_CHECKING:
    from mika.bot.client import BotApp

logger = get_logger(__name__)
_MAX_REPLY = 1990
_MEDIA_KIND = {"gif": "gifs", "sticker": "stickers", "clip": "clips"}


def _iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or datetime.now(tz=UTC).timestamp(), tz=UTC).isoformat()


def _in_scope(message: discord.Message, allowed_guilds: set[str]) -> bool:
    """True only for messages in an allowed server. DMs and other servers are out."""
    if message.guild is None:
        return False
    return not allowed_guilds or str(message.guild.id) in allowed_guilds


def _media_from_message(message: discord.Message) -> list[dict[str, Any]]:
    media: list[dict[str, Any]] = []
    for item in message.attachments:
        media.append(
            {
                "id": str(item.id),
                "url": item.url,
                "name": item.filename,
                "contentType": item.content_type,
                "size": item.size,
                "kind": "image" if (item.content_type or "").startswith("image/") else "file",
                "source": "attachment",
            }
        )
    for index, embed in enumerate(message.embeds):
        url = embed.video.url if embed.video else embed.image.url if embed.image else embed.url
        if url:
            media.append(
                {
                    "id": f"embed-{index}",
                    "url": url,
                    "sourceUrl": embed.url,
                    "name": embed.title or embed.url or f"embed-{index}",
                    "kind": "video" if embed.video else "image",
                    "source": "embed",
                    "embedType": embed.type,
                }
            )
    return media


def _media_context(media: list[dict[str, Any]]) -> str:
    if not media:
        return ""
    parts: list[str] = []
    for item in media[:4]:
        kind = str(item.get("kind") or "media")
        source = str(item.get("source") or "unknown")
        name = str(item.get("name") or "").strip()
        content_type = str(item.get("contentType") or "").strip()
        embed_type = str(item.get("embedType") or "").strip()
        label = ", ".join(value for value in (kind, source, content_type, embed_type) if value)
        if name:
            parts.append(f"- {label}: {name[:120]}")
        else:
            parts.append(f"- {label}")
    return (
        "[incoming media context: treat this socially; decide whether it reads as "
        "a joke, sarcasm, flirt, reaction bait, hype, or serious share. Do not describe "
        "the media unless the user asks.]\n" + "\n".join(parts)
    )


def _message_record(message: discord.Message, role: str, content: str) -> dict[str, Any]:
    return {
        "id": f"py-{message.id}",
        "role": role,
        "author": message.author.display_name,
        "author_id": str(message.author.id),
        "content": content,
        "created_at": _iso(message.created_at.timestamp()),
        "guild_id": str(message.guild.id) if message.guild else None,
        "guild_name": message.guild.name if message.guild else None,
        "channel_id": str(message.channel.id),
        "channel_name": getattr(message.channel, "name", None),
        "discord_message_id": str(message.id),
        "media": _media_from_message(message),
        "metadata": {
            "captureVersion": 3,
            "source": "mikav2-python",
            "authorBot": message.author.bot,
            "attachmentCount": len(message.attachments),
            "embedCount": len(message.embeds),
        },
    }


async def _send_media(message: discord.Message, media_type: str, query: str | None) -> str | None:
    if media_type not in _MEDIA_KIND or not query:
        return None
    try:
        url = await search_klipy(_MEDIA_KIND[media_type], query)
    except Exception as error:
        logger.warning("chat media search failed: %s", error)
        return None
    if not url:
        return None
    try:
        await message.channel.send(url)
    except discord.HTTPException as error:
        logger.warning("chat media send failed: %s", error)
        return None
    return url


def setup(bot: BotApp) -> None:
    """Register the on_message handler."""
    free_channels = set(get_settings().discord.response_channel_id_list)
    allowed_guilds = set(get_settings().discord.guild_id_list)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if bot.user is None or not _in_scope(message, allowed_guilds):
            return
        inbound_media = _media_from_message(message)
        content = message.clean_content or ("[media/message with no text]" if inbound_media else "")
        if message.author.id != bot.user.id:
            role = "bot" if message.author.bot else "user"
            await archive_message(_message_record(message, role, content))
        if message.author.bot:
            return
        mentioned = bot.user.mentioned_in(message)
        free_chat = str(message.channel.id) in free_channels
        if not mentioned and not free_chat:
            return
        text = message.clean_content.replace(f"@{bot.user.display_name}", "").strip()
        media_context = _media_context(inbound_media)
        if not text and not media_context:
            return
        try:
            async with message.channel.typing():
                turn = await bot.llm.reply(
                    channel_id=str(message.channel.id),
                    author_id=str(message.author.id),
                    author_name=message.author.display_name,
                    text=text,
                    media_context=media_context,
                )
        except Exception as error:
            logger.exception("reply failed: %s", error)
            return
        for emoji in turn.reactions:
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                logger.debug("reaction failed", exc_info=True)
        sent = await message.reply(turn.reply[:_MAX_REPLY] or "...")
        media_url = await _send_media(message, turn.media.kind, turn.media.query)
        now = _iso()
        await archive_message(
            {
                "id": f"py-{sent.id}",
                "role": "assistant",
                "author": get_settings().persona.name,
                "author_id": str(bot.user.id),
                "content": turn.reply,
                "created_at": now,
                "guild_id": str(message.guild.id) if message.guild else None,
                "guild_name": message.guild.name if message.guild else None,
                "channel_id": str(message.channel.id),
                "channel_name": getattr(message.channel, "name", None),
                "discord_message_id": str(sent.id),
                "reply_to_discord_message_id": str(message.id),
                "media": [
                    {
                        "kind": turn.media.kind,
                        "url": media_url,
                        "name": turn.media.query,
                        "source": "klipy",
                    }
                ]
                if media_url
                else [],
                "reactions": list(turn.reactions),
                "metadata": {
                    "captureVersion": 3,
                    "source": "mikav2-python",
                    "chosenMedia": {"type": turn.media.kind, "query": turn.media.query},
                    "turnIntent": turn.intent,
                    "turnConfidence": turn.confidence,
                    "turnSchemaVersion": turn.schema_version,
                    "turnParseStatus": turn.parse_status,
                    "inboundMediaCount": len(inbound_media),
                    "mediaContext": media_context[:600] or None,
                    "mediaSent": bool(media_url),
                },
            }
        )
        await archive_event(
            {
                "event_type": "mikav2_turn_decision",
                "created_at": now,
                "guild_id": str(message.guild.id) if message.guild else None,
                "guild_name": message.guild.name if message.guild else None,
                "channel_id": str(message.channel.id),
                "channel_name": getattr(message.channel, "name", None),
                "discord_message_id": str(sent.id),
                "related_discord_message_id": str(message.id),
                "author": get_settings().persona.name,
                "author_id": str(bot.user.id),
                "payload": {
                    "replyLength": len(turn.reply),
                    "reactions": list(turn.reactions),
                    "media": {"type": turn.media.kind, "query": turn.media.query, "url": media_url},
                    "intent": turn.intent,
                    "confidence": turn.confidence,
                    "schemaVersion": turn.schema_version,
                    "parseStatus": turn.parse_status,
                    "inboundMediaCount": len(inbound_media),
                    "mediaContext": media_context[:600] or None,
                },
            }
        )
