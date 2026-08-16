"""Roleplay reactions: hug, pat, kiss and friends, each backed by an anime GIF."""

from __future__ import annotations

from typing import Any

import discord
from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_ENDPOINT = "https://api.waifu.pics/sfw/{action}"

_ACTIONS: list[tuple[str, str, str, str]] = [
    ("hug", "Hug someone.", "{c} hugs {t}!", "{c} could really use a hug."),
    ("kiss", "Kiss someone.", "{c} kisses {t}!", "{c} blows a kiss into the void."),
    ("slap", "Slap someone.", "{c} slaps {t}!", "{c} slaps themselves. weird flex."),
    ("pat", "Pat someone on the head.", "{c} pats {t}!", "{c} pats their own head."),
    ("cuddle", "Cuddle someone.", "{c} cuddles with {t}!", "{c} cuddles a pillow."),
    ("poke", "Poke someone.", "{c} pokes {t}!", "{c} pokes the air."),
    ("bonk", "Bonk someone.", "{c} bonks {t}!", "{c} bonks themselves. ouch."),
    ("highfive", "High-five someone.", "{c} high-fives {t}!", "{c} high-fives the air."),
    ("wave", "Wave at someone.", "{c} waves at {t}!", "{c} waves at nobody in particular."),
    ("wink", "Wink at someone.", "{c} winks at {t}!", "{c} winks at the camera."),
    ("bite", "Bite someone.", "{c} bites {t}!", "{c} bites the air."),
    ("blush", "Blush at someone.", "{c} blushes at {t}!", "{c} is blushing."),
    ("smile", "Smile at someone.", "{c} smiles at {t}!", "{c} is smiling."),
    ("dance", "Dance with someone.", "{c} dances with {t}!", "{c} is dancing alone."),
    ("cry", "Cry on someone's shoulder.", "{c} cries on {t}'s shoulder.", "{c} is crying."),
    ("happy", "Be happy for someone.", "{c} is happy for {t}!", "{c} is feeling happy."),
    ("lick", "Lick someone.", "{c} licks {t}!", "{c} licks the air."),
    ("nom", "Nom someone.", "{c} noms on {t}!", "{c} noms on a snack."),
    ("glomp", "Glomp someone.", "{c} glomps {t}!", "{c} glomps the nearest pillow."),
    ("yeet", "Yeet someone into orbit.", "{c} yeets {t} into orbit!", "{c} yeets themselves."),
    ("handhold", "Hold hands.", "{c} holds {t}'s hand.", "{c} holds their own hand."),
    ("awoo", "Awoo at someone.", "{c} awoos at {t}!", "{c} awoos at the moon."),
    ("smug", "Be smug at someone.", "{c} looks smug at {t}.", "{c} is feeling smug."),
    ("cringe", "Cringe at someone.", "{c} cringes at {t}.", "{c} is cringing."),
]


def _register(
    tree: app_commands.CommandTree[Any],
    name: str,
    description: str,
    duo: str,
    solo: str,
) -> None:
    @tree.command(name=name, description=description)
    @app_commands.describe(user="who to direct it at (optional)")
    async def action(interaction: Interaction, user: discord.Member | None = None) -> None:
        await interaction.response.defer()
        caller = interaction.user.display_name
        if user is None:
            sentence = solo.format(c=caller)
        else:
            sentence = duo.format(c=caller, t=user.display_name)
        embed = helpers.embed(description=sentence)
        try:
            data = await helpers.fetch_json(_ENDPOINT.format(action=name))
            embed.set_image(url=str(data["url"]))
        except Exception as error:
            logger.warning("%s gif fetch failed: %s", name, error)
        await interaction.followup.send(embed=embed)


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the roleplay reaction commands."""
    for name, description, duo, solo in _ACTIONS:
        _register(tree, name, description, duo, solo)
