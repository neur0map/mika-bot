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
    antispam,
    basic,
    convert,
    devtools,
    extra,
    fun,
    games,
    giveaways,
    imagegen,
    images,
    info,
    infotools,
    memes,
    moderation,
    novelty,
    nsfw,
    osint,
    palette,
    presence,
    quotes,
    science,
    search,
    social,
    text,
    tickets,
    tools,
    welcome,
)

__all__ = ["register_all"]

_TOPLEVEL = (basic.setup, info.setup, images.setup, ai.setup)

_GROUPS = (
    ("text", "Transform text in fun ways.", (text.setup,)),
    ("social", "Roleplay actions with other members.", (social.setup,)),
    ("fun", "Games, jokes and random fun.", (fun.setup, novelty.setup)),
    ("game", "Mini-games to play.", (games.setup,)),
    ("image", "Image effects and meme makers.", (memes.setup,)),
    ("art", "Generate images from a prompt (free).", (imagegen.setup,)),
    ("tool", "Handy utilities and generators.", (tools.setup,)),
    ("convert", "Convert units, currency and formats.", (convert.setup,)),
    ("dev", "Developer utilities.", (devtools.setup,)),
    ("lookup", "Look up info, words, weather and more.", (infotools.setup,)),
    ("search", "Search GitHub, npm, PyPI and the web.", (search.setup,)),
    ("anime", "Anime, manga and game lookups.", (anime.setup,)),
    ("osint", "Public OSINT lookups (educational).", (osint.setup,)),
    ("math", "Math and science helpers.", (science.setup,)),
    ("quotes", "Quotes, jokes and one-liners.", (quotes.setup,)),
    ("color", "Colors, palettes and swatches.", (palette.setup,)),
    ("util", "Translate, polls, minecraft and more.", (extra.setup,)),
    ("mod", "Moderation tools (staff only).", (moderation.setup,)),
    ("admin", "Server admin: emojis and templates.", (admin.setup,)),
    ("antispam", "Anti-spam and content filters (admin).", (antispam.setup,)),
    ("greet", "Welcome messages and autorole (admin).", (welcome.setup,)),
    ("ticket", "Support tickets.", (tickets.setup,)),
    ("giveaway", "Run giveaways and raffles (admin).", (giveaways.setup,)),
    ("nsfw", "Age-gated images (NSFW channels only).", (nsfw.setup,)),
    ("anim", "Animated messages.", (animated.setup,)),
    ("presence", "Set the bot's status (admin).", (presence.setup,)),
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
