"""Anime, pokemon and waifu commands: registration plus mocked API smoke."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import anime


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(anime.setup)


async def test_setup_registers_expected_commands(tree: app_commands.CommandTree[Any]) -> None:
    names = {cmd.name for cmd in tree.walk_commands() if isinstance(cmd, app_commands.Command)}
    expected = {
        "anime",
        "manga",
        "character",
        "topanime",
        "randomanime",
        "animequote",
        "waifu",
        "neko",
        "pokemon",
        "pokedex",
    }
    assert expected <= names


async def test_anime_lookup_sends_embed(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "anime", query="naruto")
    assert sent
    assert sent.payloads[-1].get("embed") is not None


async def test_character_lookup_sends_embed(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "character", query="luffy")
    assert sent


async def test_topanime_lists_entries(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "topanime")
    assert sent
    assert "top anime" in sent.text.lower()


async def test_pokemon_lookup(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "pokemon", name="pikachu")
    assert sent
    assert sent.payloads[-1].get("embed") is not None


async def test_pokedex_lookup_by_number(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "pokedex", number=25)
    assert sent
    assert sent.payloads[-1].get("embed") is not None


async def test_waifu_sends_image_embed(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "waifu")
    assert sent
    assert sent.payloads[-1].get("embed") is not None


async def test_animequote_always_replies(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "animequote")
    assert sent
    assert sent.payloads[-1].get("embed") is not None
