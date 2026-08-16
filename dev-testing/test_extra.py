"""Translate, Minecraft, poll and HTTP utility commands run and reply."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import extra


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(extra.setup)


async def test_setup_registers_every_command(tree: app_commands.CommandTree[Any]) -> None:
    names = {
        cmd.qualified_name for cmd in tree.walk_commands() if isinstance(cmd, app_commands.Command)
    }
    expected = {
        "translate",
        "detectlang",
        "mcserver",
        "mcuuid",
        "mcskin",
        "httpcat",
        "httpstatus",
        "placeholder",
        "poll",
        "quickpoll",
        "embed",
    }
    assert expected <= names


async def test_translate(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "translate", text="hi", to_lang="es")
    assert sent


async def test_mcserver(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "mcserver", address="x")
    assert sent


async def test_httpstatus_known_code(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "httpstatus", code=404)
    assert "404" in sent.text
    assert "Not Found" in sent.text


async def test_httpstatus_unknown_code(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "httpstatus", code=999)
    assert "Unknown" in sent.text


async def test_poll_lists_options(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "poll", question="best snack?", options="a,b,c")
    assert sent
    assert "best snack?" in sent.text
    assert "a" in sent.text
    assert "b" in sent.text
    assert "c" in sent.text


async def test_poll_without_options_falls_back_to_yes_no(
    tree: app_commands.CommandTree[Any],
) -> None:
    sent = await invoke(tree, "poll", question="ship it?")
    assert "yes" in sent.text
    assert "no" in sent.text


async def test_embed_sends_title_and_description(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "embed", title="t", description="d")
    assert "t" in sent.text
    assert "d" in sent.text
