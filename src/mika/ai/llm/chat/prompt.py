"""System-prompt and persona assembly from settings, the persona file, and memory."""

from __future__ import annotations

from mika.core.config import get_settings


def load_persona() -> str:
    """Return the persona text: an identity line plus the editable persona file."""
    settings = get_settings()
    persona_file = settings.persona.file
    base = persona_file.read_text(encoding="utf-8") if persona_file.exists() else ""
    intro = (
        f"You are {settings.persona.name}, a friendly Discord bot. "
        f"Always stay in character as {settings.persona.name}. Keep replies concise. "
        "For anything time-sensitive, or any specific person, product, or name you are "
        "not certain about, use the web_search tool before answering. Never invent "
        "facts; if a search turns up nothing, say so plainly."
    )
    return f"{intro}\n\n{base}".strip()


def build_system_prompt(memory_context: str = "") -> str:
    """Combine the persona with any recalled memory into one system message."""
    persona = load_persona()
    if memory_context.strip():
        return f"{persona}\n\n# Context that may help your reply\n{memory_context}"
    return persona
