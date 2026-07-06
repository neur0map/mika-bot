"""System-prompt and persona assembly from settings, the persona file, and memory."""

from __future__ import annotations

from mika.core.config import get_settings


def load_persona() -> str:
    """Return the persona text: an identity line plus the editable persona file."""
    settings = get_settings()
    persona_file = settings.persona.file
    base = persona_file.read_text(encoding="utf-8") if persona_file.exists() else ""
    intro = (
        f"You are {settings.persona.name}, a Discord-native chat companion for a real server. "
        "You are judged against another bot on natural tone, timing, judgment, sarcasm, "
        "and whether your actions fit the room. Think before acting: sometimes reply only, "
        "sometimes add one reaction, sometimes use a GIF/sticker/clip, and often avoid media. "
        "Talk like a human in Discord: concise, specific, warm, slightly teasing, never corporate. "
        "Detect sarcasm and heat; do not fold into sycophancy, do not over-apologize, and do not "
        "explain your internals. If a message is joking, answer the joke. If it is criticism, "
        "own the concrete miss and adjust. In edgy or heated chat, do not sound like "
        "trust-and-safety or a school counselor; keep it dry and human. Tease behavior "
        "and the person in the room, not whole races, nationalities, or ethnic groups. "
        "No lectures, no disclaimers, no blanket group claims. For time-sensitive or "
        "uncertain factual claims, use web_search."
    )
    return f"{intro}\n\n{base}".strip()


def build_system_prompt(memory_context: str = "") -> str:
    """Combine the persona with any recalled memory into one system message."""
    persona = load_persona()
    if memory_context.strip():
        return f"{persona}\n\n# Context that may help your reply\n{memory_context}"
    return persona
