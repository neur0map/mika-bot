"""Info and utility commands: smoke and shape checks."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_interaction, tree_for

from mika.bot.commands import infotools


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(infotools.setup)


async def test_setup_registers_every_command(tree: app_commands.CommandTree[Any]) -> None:
    names = {
        cmd.qualified_name for cmd in tree.walk_commands() if isinstance(cmd, app_commands.Command)
    }
    expected = {
        "channelinfo",
        "roleinfo",
        "emojiinfo",
        "serverroles",
        "serverchannels",
        "membercount",
        "boosts",
        "servericon",
        "serverbanner",
        "weather",
        "urban",
        "define",
        "crypto",
        "wikipedia",
        "color",
    }
    assert expected <= names


async def test_serverroles_lists_role_names(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "serverroles")
    assert sent
    assert "Members" in sent.text


async def test_channelinfo_defaults_to_current_channel(
    tree: app_commands.CommandTree[Any],
) -> None:
    sent = await invoke(tree, "channelinfo")
    assert sent
    assert "general" in sent.text


async def test_weather_uses_city(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "weather", city="london")
    assert sent
    assert "london" in sent.text.lower()


async def test_color_renders_hex(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "color", hex_code="#ff0000")
    assert sent
    assert "ff0000" in sent.text.lower()
    assert "R=255" in sent.text


async def test_color_rejects_bad_input(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "color", hex_code="not-a-color")
    assert "hex" in sent.text.lower()


async def test_membercount_outside_guild_denies(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction(guild=None)
    sent = await invoke(tree, "membercount", interaction=inter)
    assert "server" in sent.text.lower()


async def test_boosts_reports_count(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "boosts")
    assert "boost" in sent.text.lower()
