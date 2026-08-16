"""Anime, manga, character and pokemon lookups backed by keyless public APIs."""

from __future__ import annotations

import secrets
from typing import Any

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_JIKAN = "https://api.jikan.moe/v4"
_WAIFU = "https://api.waifu.pics/sfw"
_POKEAPI = "https://pokeapi.co/api/v2/pokemon"
_ANIMECHAN = "https://animechan.io/api/v1/quotes/random"

_SYNOPSIS_CAP = 600
_FALLBACK_QUOTES: tuple[tuple[str, str, str], ...] = (
    (
        "People's lives don't end when they die. It ends when they lose faith.",
        "Itachi Uchiha",
        "Naruto",
    ),
    ("A lesson without pain is meaningless.", "Edward Elric", "Fullmetal Alchemist"),
    ("If you don't take risks, you can't create a future.", "Monkey D. Luffy", "One Piece"),
    (
        "Hard work is worthless for those that don't believe in themselves.",
        "Naruto Uzumaki",
        "Naruto",
    ),
    (
        "The world isn't perfect. But it's there for us doing the best it can.",
        "Roy Mustang",
        "Fullmetal Alchemist",
    ),
)


def _clip_synopsis(text: str) -> str:
    cleaned = text.strip()
    if len(cleaned) <= _SYNOPSIS_CAP:
        return cleaned
    return cleaned[: _SYNOPSIS_CAP - 1] + "\u2026"


def _image_url(entry: Any) -> str:
    try:
        return str(entry["images"]["jpg"]["image_url"])
    except Exception:
        return ""


def _media_embed(entry: Any, kind: str) -> Any:
    title = str(entry.get("title") or entry.get("name") or "unknown")
    description = _clip_synopsis(str(entry.get("synopsis") or entry.get("about") or ""))
    emb = helpers.embed(title=title, description=description or None)
    score = entry.get("score")
    if score:
        emb.add_field(name="score", value=str(score), inline=True)
    if kind == "anime":
        episodes = entry.get("episodes")
        if episodes:
            emb.add_field(name="episodes", value=str(episodes), inline=True)
    if kind == "manga":
        chapters = entry.get("chapters")
        if chapters:
            emb.add_field(name="chapters", value=str(chapters), inline=True)
    picture = _image_url(entry)
    if picture:
        emb.set_image(url=picture)
    return emb


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the anime and pokemon lookup commands."""

    @tree.command(name="anime", description="Look up an anime on MyAnimeList.")
    @app_commands.describe(query="title to search for")
    async def anime(interaction: Interaction, query: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"{_JIKAN}/anime", q=query, limit=1)
            entry = data["data"][0]
        except Exception as error:
            logger.warning("anime fetch failed: %s", error)
            await interaction.followup.send("couldn't find that anime")
            return
        await interaction.followup.send(embed=_media_embed(entry, "anime"))

    @tree.command(name="manga", description="Look up a manga on MyAnimeList.")
    @app_commands.describe(query="title to search for")
    async def manga(interaction: Interaction, query: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"{_JIKAN}/manga", q=query, limit=1)
            entry = data["data"][0]
        except Exception as error:
            logger.warning("manga fetch failed: %s", error)
            await interaction.followup.send("couldn't find that manga")
            return
        await interaction.followup.send(embed=_media_embed(entry, "manga"))

    @tree.command(name="character", description="Look up an anime/manga character.")
    @app_commands.describe(query="character name to search for")
    async def character(interaction: Interaction, query: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"{_JIKAN}/characters", q=query, limit=1)
            entry = data["data"][0]
        except Exception as error:
            logger.warning("character fetch failed: %s", error)
            await interaction.followup.send("couldn't find that character")
            return
        await interaction.followup.send(embed=_media_embed(entry, "character"))

    @tree.command(name="topanime", description="Top 10 anime on MyAnimeList right now.")
    async def topanime(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"{_JIKAN}/top/anime", limit=10)
            entries = list(data["data"])
        except Exception as error:
            logger.warning("topanime fetch failed: %s", error)
            await interaction.followup.send("the leaderboard is napping")
            return
        lines = [
            f"{idx}. {entry.get('title') or 'unknown'}" for idx, entry in enumerate(entries, 1)
        ]
        emb = helpers.embed(title="top anime", description="\n".join(lines) or "nothing to show")
        await interaction.followup.send(embed=emb)

    @tree.command(name="randomanime", description="A random anime from MyAnimeList.")
    async def randomanime(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"{_JIKAN}/random/anime")
            entry = data["data"]
        except Exception as error:
            logger.warning("randomanime fetch failed: %s", error)
            await interaction.followup.send("the random pick failed, try again")
            return
        await interaction.followup.send(embed=_media_embed(entry, "anime"))

    @tree.command(name="animequote", description="A random anime quote.")
    async def animequote(interaction: Interaction) -> None:
        await interaction.response.defer()
        quote, who, show = secrets.choice(_FALLBACK_QUOTES)
        try:
            data = await helpers.fetch_json(_ANIMECHAN)
            payload = data.get("data") if hasattr(data, "get") else data
            payload = payload or data
            raw_quote = payload.get("content") or payload.get("quote")
            raw_char = payload.get("character")
            raw_show = payload.get("anime")
            if raw_quote:
                quote = str(raw_quote)
            if raw_char:
                who = str(raw_char.get("name") if hasattr(raw_char, "get") else raw_char)
            if raw_show:
                show = str(raw_show.get("name") if hasattr(raw_show, "get") else raw_show)
        except Exception as error:
            logger.warning("animequote fetch failed: %s", error)
        emb = helpers.embed(description=f"> {quote}\n\u2014 **{who}** ({show})")
        await interaction.followup.send(embed=emb)

    @tree.command(name="waifu", description="A wholesome waifu picture.")
    async def waifu(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"{_WAIFU}/waifu")
            url = str(data["url"])
        except Exception as error:
            logger.warning("waifu fetch failed: %s", error)
            await interaction.followup.send("the waifu well is dry")
            return
        emb = helpers.embed()
        emb.set_image(url=url)
        await interaction.followup.send(embed=emb)

    @tree.command(name="neko", description="A cat-eared neko picture.")
    async def neko(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"{_WAIFU}/neko")
            url = str(data["url"])
        except Exception as error:
            logger.warning("neko fetch failed: %s", error)
            await interaction.followup.send("no nekos available")
            return
        emb = helpers.embed()
        emb.set_image(url=url)
        await interaction.followup.send(embed=emb)

    @tree.command(name="pokemon", description="Look up a Pokemon by name.")
    @app_commands.describe(name="pokemon name, e.g. pikachu")
    async def pokemon(interaction: Interaction, name: str) -> None:
        await interaction.response.defer()
        slug = name.strip().lower()
        try:
            data = await helpers.fetch_json(f"{_POKEAPI}/{slug}")
            await interaction.followup.send(embed=_pokemon_embed(data))
        except Exception as error:
            logger.warning("pokemon fetch failed: %s", error)
            await interaction.followup.send("couldn't catch that pokemon")

    @tree.command(name="pokedex", description="Look up a Pokemon by national dex number.")
    @app_commands.describe(number="national dex number, 1-1025")
    async def pokedex(interaction: Interaction, number: int) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"{_POKEAPI}/{number}")
            await interaction.followup.send(embed=_pokemon_embed(data))
        except Exception as error:
            logger.warning("pokedex fetch failed: %s", error)
            await interaction.followup.send("nothing at that dex entry")


def _pokemon_embed(data: Any) -> Any:
    name = str(data.get("name") or "unknown").title()
    dex = data.get("id")
    title = f"#{dex} {name}" if dex else name
    emb = helpers.embed(title=title)
    types = data.get("types") or []
    type_names: list[str] = []
    for slot in types:
        try:
            type_names.append(str(slot["type"]["name"]))
        except Exception:
            continue
    if type_names:
        emb.add_field(name="types", value=", ".join(type_names), inline=True)
    height = data.get("height")
    weight = data.get("weight")
    if height:
        emb.add_field(name="height", value=f"{int(height) / 10:.1f} m", inline=True)
    if weight:
        emb.add_field(name="weight", value=f"{int(weight) / 10:.1f} kg", inline=True)
    sprite = ""
    try:
        sprite = str(data["sprites"]["front_default"])
    except Exception:
        sprite = ""
    if sprite:
        emb.set_thumbnail(url=sprite)
    return emb
