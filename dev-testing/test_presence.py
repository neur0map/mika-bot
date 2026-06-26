"""Bot presence commands: admin gating and presence dispatch."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_interaction, make_member, tree_for

from mika.bot.commands import presence


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(presence.setup)


async def test_playing_sets_presence(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction()
    await invoke(tree, "playing", interaction=inter, text="a game")
    inter.client.change_presence.assert_awaited_once()


async def test_setstatus_valid(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction()
    sent = await invoke(tree, "setstatus", interaction=inter, status="idle")
    assert "idle" in sent.text


async def test_setstatus_invalid(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "setstatus", status="bogus")
    assert "online" in sent.text.lower()


async def test_non_admin_denied(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction(user=make_member(admin=False))
    sent = await invoke(tree, "playing", interaction=inter, text="x")
    inter.client.change_presence.assert_not_awaited()
    assert "administrator" in sent.text.lower()
