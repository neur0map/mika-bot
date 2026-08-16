"""on_message: route mentions and free-chat channels to the AI brain."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import discord

from mika.bot.media import search_klipy
from mika.conversation.actions import ActionContext
from mika.conversation.contracts.media import MediaAsset
from mika.conversation.trace_service import TurnTraceService
from mika.core.config import get_settings
from mika.core.logging import get_logger
from mika.discord.execution.archive import build_visible_records
from mika.discord.execution.executor import DiscordActionExecutor
from mika.discord.ingress.envelope import envelope_from_message
from mika.discord.ingress.media import media_from_message
from mika.persistence.conversations.traces import TurnTraceRepository
from mika.persistence.engine import session
from mika.persistence.shared_archive import archive_event, archive_message

if TYPE_CHECKING:
    from mika.bot.client import BotApp

logger = get_logger(__name__)


def _iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or datetime.now(tz=UTC).timestamp(), tz=UTC).isoformat()


def _in_scope(message: discord.Message, allowed_guilds: set[str]) -> bool:
    """True only for messages in an allowed server. DMs and other servers are out."""
    if message.guild is None:
        return False
    return not allowed_guilds or str(message.guild.id) in allowed_guilds


def _media_from_message(message: discord.Message) -> list[dict[str, Any]]:
    return _media_records(media_from_message(message))


def _media_records(assets: tuple[MediaAsset, ...]) -> list[dict[str, Any]]:
    return [
        {
            "url": asset.url,
            "name": asset.filename,
            "contentType": asset.content_type,
            "kind": asset.kind,
            "source": asset.source,
            "width": asset.width,
            "height": asset.height,
        }
        for asset in assets
    ]


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
        "[incoming media context: images are attached for you to look at. Treat them "
        "socially; decide whether it reads as a joke, sarcasm, flirt, reaction bait, "
        "hype, or serious share. Do not narrate or caption the media unless the user "
        "asks what it is - then answer plainly.]\n" + "\n".join(parts)
    )


_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _media_urls(media: list[dict[str, Any]]) -> list[str]:
    """Pick the links a vision-capable model can actually look at.

    Attachments carry a content type; embeds (Tenor/Giphy links) usually do not,
    so fall back to the file extension on the URL.
    """
    urls: list[str] = []
    for item in media:
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        content_type = str(item.get("contentType") or "")
        looks_like_image = url.split("?")[0].lower().endswith(_IMAGE_SUFFIXES)
        if content_type.startswith("image/") or looks_like_image:
            urls.append(url)
    return urls


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


async def _persist_turn_trace(trace: TurnTraceService) -> None:
    """Persist diagnostics without affecting visible Discord behavior."""
    try:
        async with session() as database:
            await trace.persist(TurnTraceRepository(database))
    except Exception:
        logger.warning("turn trace persistence failed", exc_info=True)


def setup(bot: BotApp) -> None:
    """Register the on_message handler."""
    free_channels = set(get_settings().discord.response_channel_id_list)
    allowed_guilds = set(get_settings().discord.guild_id_list)
    executor = DiscordActionExecutor(search_klipy)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if bot.user is None or not _in_scope(message, allowed_guilds):
            return
        envelope = envelope_from_message(message, bot.user.id)
        inbound_media = _media_records(envelope.visual_inputs)
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
        trace = TurnTraceService(str(uuid4()), str(message.id), str(message.channel.id))
        trace.record(
            "ingress",
            "ready",
            details={"media_count": len(inbound_media), "mentioned": mentioned},
        )
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
                    media_urls=_media_urls(inbound_media),
                    trace=trace,
                )
        except Exception as error:
            logger.exception("reply failed: %s", error)
            await _persist_turn_trace(trace)
            return
        context = ActionContext(
            channel_id=str(message.channel.id),
            mentioned=mentioned,
            direct_question=mentioned or text.rstrip().endswith("?"),
        )
        plan = bot.action_planner.plan(turn, context)
        trace.record(
            "policy",
            "silent" if plan.is_silent else "allowed",
            reason=plan.silence_reason,
        )
        execution = await executor.execute(message, plan)
        bot.action_planner.record_visible(
            plan,
            execution,
            channel_id=context.channel_id,
        )
        now = _iso()
        message_record, event_record = build_visible_records(
            message,
            plan,
            execution,
            bot_user_id=str(bot.user.id),
            persona_name=get_settings().persona.name,
            inbound_media_count=len(inbound_media),
            media_context=media_context,
            created_at=now,
        )
        if message_record is not None:
            await archive_message(message_record)
        await archive_event(event_record)
        trace.record(
            "execution",
            "visible" if message_record is not None else "silent",
            details={
                "reply_sent": execution.reply_message_id is not None,
                "reaction_count": len(execution.applied_reactions),
                "media_sent": execution.media_url is not None,
                "failure_count": len(execution.failures),
            },
        )
        await _persist_turn_trace(trace)
