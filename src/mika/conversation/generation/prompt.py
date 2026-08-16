"""Prompt composition for concise structured Discord turns."""

from __future__ import annotations

from mika.ai.llm.providers.base import Message


class PromptComposer:
    """Build user and schema instructions without provider state."""

    def user_input(self, text: str, media_context: str = "") -> str:
        """Combine visible text and normalized media context."""
        clean_text = text.strip()
        clean_media = media_context.strip()
        if clean_text and clean_media:
            return f"{clean_text}\n{clean_media}"
        return clean_text or clean_media or "[media/message with no text]"

    def generation_input(self, user_input: str, history: list[Message]) -> str:
        """Append bounded assistant wording that the next turn should not repeat."""
        phrases = [
            str(item.get("content") or "").strip()[:180]
            for item in reversed(history)
            if item.get("role") == "assistant" and str(item.get("content") or "").strip()
        ][:4]
        if not phrases:
            return user_input
        lines = "\n".join(f"- {phrase}" for phrase in phrases)
        return (
            f"{user_input}\n\n[recent assistant wording to avoid repeating; keep the same "
            f"personality but vary rhythm, joke shape, and phrasing.]\n{lines}"
        )

    def structured(self, user_text: str) -> str:
        """Request the stable social-turn JSON contract."""
        return (
            f"{user_text}\n\nReturn strict JSON only with keys: schema_version, reply, reactions, "
            "media, intent, confidence. schema_version is 'mika_turn.v2'. reply is the Discord "
            "message text and may be empty when a reaction or media choice is enough. reactions "
            "is 0-1 emoji from [👍,👎,😭,💀,👀,🤔,😂,😬,❤️,🔥,✅]. media is "
            "{type:'none'|'gif'|'sticker'|'clip', query:null|string}. intent is one of chat, joke, "
            "sarcasm, flirt, hype, comfort, question, criticism, media_reaction, serious, silence. "
            "confidence is the social-read confidence. Sound like a concise Discord member, not "
            "an assistant. For incoming media, use what happens in it as conversational context; "
            "do not describe it unless asked. Choose a short reply, reaction, matching media, or "
            "silence. No explanation outside the JSON."
        )
