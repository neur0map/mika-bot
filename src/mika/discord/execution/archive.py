"""Build privacy-conscious archive records from visible Discord results."""

from __future__ import annotations

from typing import Any

from mika.conversation.actions import ActionPlan, ExecutionResult


def build_visible_records(
    message: Any,
    plan: ActionPlan,
    execution: ExecutionResult,
    *,
    bot_user_id: str,
    persona_name: str,
    inbound_media_count: int,
    media_context: str,
    created_at: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return a visible message record plus an always-present decision event."""
    guild = message.guild
    channel = message.channel
    guild_id = str(guild.id) if guild else None
    guild_name = guild.name if guild else None
    reply_id = execution.reply_message_id
    media = (
        [
            {
                "kind": plan.media.kind,
                "url": execution.media_url,
                "name": plan.media.query,
                "source": "klipy",
            }
        ]
        if plan.media is not None and execution.media_url is not None
        else []
    )
    visible = bool(reply_id or execution.applied_reactions or execution.media_url)
    message_record: dict[str, Any] | None = None
    if visible:
        action_id = reply_id or f"action-{message.id}"
        message_record = {
            "id": f"py-{action_id}",
            "role": "assistant",
            "author": persona_name,
            "author_id": bot_user_id,
            "content": plan.reply if reply_id else "",
            "created_at": created_at,
            "guild_id": guild_id,
            "guild_name": guild_name,
            "channel_id": str(channel.id),
            "channel_name": getattr(channel, "name", None),
            "discord_message_id": reply_id,
            "reply_to_discord_message_id": str(message.id),
            "media": media,
            "reactions": list(execution.applied_reactions),
            "metadata": _payload(plan, execution, inbound_media_count, media_context),
        }
    event_record = {
        "event_type": "mikav2_turn_decision",
        "created_at": created_at,
        "guild_id": guild_id,
        "guild_name": guild_name,
        "channel_id": str(channel.id),
        "channel_name": getattr(channel, "name", None),
        "discord_message_id": reply_id,
        "related_discord_message_id": str(message.id),
        "author": persona_name,
        "author_id": bot_user_id,
        "payload": _payload(plan, execution, inbound_media_count, media_context),
    }
    return message_record, event_record


def _payload(
    plan: ActionPlan,
    execution: ExecutionResult,
    inbound_media_count: int,
    media_context: str,
) -> dict[str, Any]:
    return {
        "replyLength": len(plan.reply) if execution.reply_message_id else 0,
        "reactions": list(execution.applied_reactions),
        "media": {
            "type": plan.media.kind if plan.media else None,
            "query": plan.media.query if plan.media else None,
            "url": execution.media_url,
        },
        "intent": plan.intent,
        "confidence": plan.confidence,
        "actionOnly": not bool(execution.reply_message_id),
        "inboundMediaCount": inbound_media_count,
        "mediaContext": media_context[:600] or None,
        "silenceReason": plan.silence_reason,
        "failures": list(execution.failures),
    }
