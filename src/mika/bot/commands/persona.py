"""Switch and create the bot's personality (admin). Memory is always kept."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from discord import Interaction, app_commands

from mika.ai.learning.persona_forge import forge_persona, user_personas_dir
from mika.bot.commands import helpers
from mika.core.config import get_settings

if TYPE_CHECKING:
    from mika.bot.client import BotApp

_BUNDLED = Path("config/personas")


def _all_presets() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for directory in (_BUNDLED, user_personas_dir()):
        if directory.is_dir():
            for path in sorted(directory.glob("*.md")):
                found[path.stem] = path
    return found


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the personality commands."""

    @tree.command(name="list", description="List the available personalities.")
    async def list_personas(interaction: Interaction) -> None:
        names = sorted(_all_presets())
        await helpers.send(interaction, "Personalities: " + (", ".join(names) or "none found"))

    @tree.command(name="preview", description="Preview a personality's prompt.")
    @app_commands.describe(name="personality name")
    async def preview(interaction: Interaction, name: str) -> None:
        path = _all_presets().get(name.lower())
        if path is None:
            await helpers.deny(interaction, f"unknown; try: {', '.join(sorted(_all_presets()))}")
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
        source = _all_presets().get(name.lower())
        if source is None:
            await helpers.deny(interaction, f"unknown; try: {', '.join(sorted(_all_presets()))}")
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

    @tree.command(
        name="create", description="Generate a new personality from a description (admin)."
    )
    @app_commands.describe(name="a name for the personality", description="describe the character")
    async def create(interaction: Interaction, name: str, description: str) -> None:
        if not helpers.has_perms(interaction, "manage_guild"):
            await helpers.deny(interaction, "you need the Manage Server permission")
            return
        await interaction.response.defer(ephemeral=True)
        bot = cast("BotApp", interaction.client)
        path = await forge_persona(bot.llm, name, description)
        await interaction.followup.send(
            f"created **{path.stem}** - switch to it with /persona set {path.stem}", ephemeral=True
        )
