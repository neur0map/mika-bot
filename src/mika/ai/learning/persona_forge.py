"""Persona generation: turn a short description into a usable persona file.

The streamlined persona-creation flow. It uses a preset 'creator' model (strong but
cost-balanced) through the operator's OpenRouter key, so the operator only has to pick
their own main chat model. Generated personas are saved alongside the bundled presets.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from mika.core.config import get_settings
from mika.core.env_file import write_env
from mika.core.logging import get_logger
from mika.core.paths import data_dir

if TYPE_CHECKING:
    from mika.ai.llm.client import LLMClient

logger = get_logger(__name__)

PRESET_CREATOR_MODEL = "anthropic/claude-3.5-sonnet"
_ARCHITECT = (
    "You are a persona architect for a chat bot. Given a NAME (often a famous person or "
    "fictional character) and optional notes, write a persona file in markdown with these "
    "sections: '# Persona', '## Identity', '## Tone', '## Boundaries'. If the name is a known "
    "character, capture their voice, mannerisms and signature phrases faithfully. Keep it "
    "tight and characterful. Never name a specific AI model or provider. Output only markdown."
)
_FALLBACK = (
    "# Persona\n\n## Identity\nA friendly, helpful companion.\n\n"
    "## Tone\n- Natural and concise.\n\n"
    "## Boundaries\n- Stay in character; never claim to be a specific AI model.\n"
)


def user_personas_dir() -> Path:
    """Where generated personas are saved (writable, separate from bundled presets)."""
    return data_dir() / "personas"


def slugify(name: str) -> str:
    """A safe filename stem for a persona name."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "custom"


async def forge_persona(client: LLMClient, name: str, description: str) -> Path:
    """Generate a persona file from a description and save it. Returns the path."""
    text = await client.summarize(
        _ARCHITECT, f"Name: {name}\nDescription: {description}", model=PRESET_CREATOR_MODEL
    )
    directory = user_personas_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slugify(name)}.md"
    path.write_text(text.strip() or _FALLBACK, encoding="utf-8")
    logger.info("generated persona %s", path.name)
    return path


_BUNDLED = Path("config/personas")


def all_personas() -> dict[str, Path]:
    """Bundled presets plus generated personas, keyed by name."""
    found: dict[str, Path] = {}
    for directory in (_BUNDLED, user_personas_dir()):
        if directory.is_dir():
            for path in sorted(directory.glob("*.md")):
                found[path.stem] = path
    return found


def persona_summary(path: Path) -> str:
    """A one-line description: the first line under the '## Identity' heading."""
    capture = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## identity"):
            capture = True
        elif capture and stripped and not stripped.startswith("#"):
            return stripped
    return "A custom personality."


def activate(name: str) -> bool:
    """Make a persona the active one (copy it into place, record the name). Instant."""
    source = all_personas().get(name.lower())
    if source is None:
        return False
    target = get_settings().persona.file
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    write_env({"MIKA_PERSONA_ACTIVE": name.lower()})
    return True
