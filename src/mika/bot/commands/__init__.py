"""Slash commands. Common ones stay top-level; the rest group under the 100-command
cap (e.g. /text reverse, /mod ban). register_all wires everything to the tree."""

from __future__ import annotations

from typing import Any, cast

from discord import app_commands

from mika.bot.commands import (
    admin,
    ai,
    animated,
    anime,
    basic,
    convert,
    devtools,
    fun,
    games,
    images,
    info,
    infotools,
    memes,
    moderation,
    novelty,
    nsfw,
    search,
    social,
    text,
    tools,
)

__all__ = ["register_all"]

_TOPLEVEL = (basic.setup, info.setup, images.setup, ai.setup)

_GROUPS = (
    ("text", "Transform text in fun ways.", (text.setup,)),
    ("social", "Roleplay actions with other members.", (social.setup,)),
    ("fun", "Games, jokes and random fun.", (fun.setup, novelty.setup)),
    ("game", "Mini-games to play.", (games.setup,)),
    ("image", "Image effects and meme makers.", (memes.setup,)),
    ("tool", "Handy utilities and generators.", (tools.setup,)),
    ("convert", "Convert units, currency and formats.", (convert.setup,)),
    ("dev", "Developer utilities.", (devtools.setup,)),
    ("lookup", "Look up info, words, weather and more.", (infotools.setup,)),
    ("search", "Search GitHub, npm, PyPI and the web.", (search.setup,)),
    ("anime", "Anime, manga and game lookups.", (anime.setup,)),
    ("mod", "Moderation tools (staff only).", (moderation.setup,)),
    ("admin", "Server admin: emojis and templates.", (admin.setup,)),
    ("nsfw", "Age-gated images (NSFW channels only).", (nsfw.setup,)),
    ("anim", "Animated messages.", (animated.setup,)),
)


def register_all(tree: app_commands.CommandTree[Any]) -> None:
    """Attach top-level commands and grouped subcommands to the command tree."""
    for setup in _TOPLEVEL:
        setup(tree)
    for name, description, setups in _GROUPS:
        group = app_commands.Group(name=name, description=description)
        target = cast("app_commands.CommandTree[Any]", group)
        for setup in setups:
            setup(target)
        tree.add_command(group)
