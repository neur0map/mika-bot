"""Switch the bot's personality between bundled presets (admin). Memory is kept."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.config import get_settings

_PRESETS_DIR = Path("config/personas")


def _preset_names() -> list[str]:
    if not _PRESETS_DIR.is_dir():
        return []
    return sorted(path.stem for path in _PRESETS_DIR.glob("*.md"))


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the personality commands."""

    @tree.command(name="list", description="List the available personalities.")
    async def list_personas(interaction: Interaction) -> None:
        names = _preset_names()
        await helpers.send(interaction, "Personalities: " + (", ".join(names) or "none found"))

    @tree.command(name="preview", description="Preview a personality's prompt.")
    @app_commands.describe(name="personality name")
    async def preview(interaction: Interaction, name: str) -> None:
        path = _PRESETS_DIR / f"{name.lower()}.md"
        if not path.is_file():
            await helpers.deny(interaction, f"unknown; try: {', '.join(_preset_names())}")
            return
        await helpers.send(
            interaction, helpers.clip(path.read_text(encoding="utf-8")), ephemeral=True
        )

    @tree.command(name="set", description="Switch the bot's personality. Keeps all memory.")
    @app_commands.describe(name="personality name")
    async def set_persona(interaction: Interaction, name: str) -> None:
        if not helpers.has_perms(interaction, "manage_guild"):
            await helpers.deny(interaction, "you need the Manage Server permission")
            return
        source = _PRESETS_DIR / f"{name.lower()}.md"
        if not source.is_file():
            await helpers.deny(interaction, f"unknown; try: {', '.join(_preset_names())}")
            return
        target = get_settings().persona.file
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        await helpers.send(
            interaction,
            f"personality is now **{name.lower()}** - memory is untouched",
            ephemeral=True,
        )

    @tree.command(name="current", description="Show the active personality.")
    async def current(interaction: Interaction) -> None:
        path = get_settings().persona.file
        text = (
            path.read_text(encoding="utf-8") if path.is_file() else "(using the built-in default)"
        )
        await helpers.send(interaction, helpers.clip(text), ephemeral=True)
