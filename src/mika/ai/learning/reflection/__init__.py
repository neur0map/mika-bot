"""Weekly self-reflection: review recent chats and note lessons to improve replies."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from mika.core.logging import get_logger
from mika.persistence.repositories.config import get_setting, set_setting
from mika.persistence.repositories.messages import recent_messages

if TYPE_CHECKING:
    from mika.ai.llm.client import LLMClient

logger = get_logger(__name__)

_GLOBAL = 0
_INSTRUCTION = (
    "You review a chat bot's recent messages and write 3 to 5 short, specific lessons "
    "to improve future replies - tone, accuracy, and helpfulness. Output a bullet list."
)

__all__ = ["last_reflection", "run_reflection"]


async def run_reflection(client: LLMClient) -> str:
    """Summarize recent conversations into improvement notes and store them."""
    lines = await recent_messages(80)
    content = "\n".join(lines) if lines else "No recent activity to review."
    lessons = await client.summarize(_INSTRUCTION, content)
    if lessons:
        await set_setting(_GLOBAL, "last_reflection", lessons)
        await set_setting(_GLOBAL, "last_reflection_at", datetime.now(tz=UTC).isoformat())
        logger.info("self-reflection stored (%d chars)", len(lessons))
    return lessons or "nothing to reflect on yet"


async def last_reflection() -> tuple[str | None, str | None]:
    """Return the latest stored reflection text and its timestamp."""
    text = await get_setting(_GLOBAL, "last_reflection")
    when = await get_setting(_GLOBAL, "last_reflection_at")
    return text, when


async def auto_enabled() -> bool:
    """Whether the weekly reflection loop should run."""
    return (await get_setting(_GLOBAL, "reflection_auto")) == "1"
