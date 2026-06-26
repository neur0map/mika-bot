"""The settings exposed in the web editor: which env keys, how to render them.

A flat catalog drives the settings form so the page stays declarative. Secrets are
never sent to the browser - their fields render empty and only update when filled in.
Keys flagged ``restart`` need the bot to reconnect; the page surfaces that.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Field:
    """One editable setting."""

    key: str  # the .env variable name
    label: str
    group: str
    kind: str = "text"  # text | secret | bool | number
    help: str = ""
    restart: bool = False


CATALOG: tuple[Field, ...] = (
    Field("MIKA_PERSONA_NAME", "Display name", "Identity", help="The name users see."),
    Field(
        "MIKA_LLM_MODEL",
        "Chat model",
        "AI",
        help="Any OpenRouter model, e.g. anthropic/claude-3.5-sonnet.",
    ),
    Field("MIKA_LLM_API_KEY", "AI key (OpenRouter)", "AI", kind="secret", restart=True),
    Field("MIKA_LLM_TEMPERATURE", "Creativity (0.0-1.0)", "AI", kind="number"),
    Field("MIKA_LLM_MAX_TOKENS", "Max reply length (tokens)", "AI", kind="number"),
    Field("MIKA_TOOLS_WEB_SEARCH_ENABLED", "Web search", "AI", kind="bool"),
    Field("MIKA_MEMORY_RECENT_WINDOW", "Short-term memory (messages)", "Memory", kind="number"),
    Field(
        "MIKA_MEMORY_HONCHO_ENABLED",
        "Long-term memory (Honcho)",
        "Memory",
        kind="bool",
        help="Needs the Honcho stack - see docs/HONCHO-MEMORY.md.",
        restart=True,
    ),
    Field("DISCORD_TOKEN", "Bot token", "Discord", kind="secret", restart=True),
    Field("DISCORD_CLIENT_ID", "Application ID", "Discord"),
    Field(
        "DISCORD_GUILD_IDS",
        "Server IDs",
        "Discord",
        help="Comma-separated. Blank = every server.",
        restart=True,
    ),
    Field(
        "DISCORD_RESPONSE_CHANNEL_IDS",
        "Free-chat channels",
        "Discord",
        help="Comma-separated channel IDs the bot replies in without @mention.",
        restart=True,
    ),
    Field("MIKA_MEDIA_KLIPY_API_KEY", "GIF search key (Klipy)", "Features", kind="secret"),
)


def groups() -> list[str]:
    """Catalog group names in display order, de-duplicated."""
    seen: list[str] = []
    for field in CATALOG:
        if field.group not in seen:
            seen.append(field.group)
    return seen
