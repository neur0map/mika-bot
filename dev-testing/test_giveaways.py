"""Giveaway commands: instant raffle, reaction start and host-ended draws."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_interaction, make_member, tree_for

from mika.bot.commands import giveaways


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(giveaways.setup)


async def test_pick_chooses_from_list(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "pick", prize="nitro", entries="alice, bob, carol")
    assert any(name in sent.text for name in ("alice", "bob", "carol"))


async def test_pick_empty_denied(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "pick", prize="x", entries="   ")
    assert "entries" in sent.text.lower()


async def test_start_posts_embed(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "start", prize="nitro")
    assert "giveaway" in sent.text.lower()


async def test_end_bad_id(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "end", message_id="notanumber")
    assert "id" in sent.text.lower()


async def test_non_admin_start_denied(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction(user=make_member(admin=False))
    sent = await invoke(tree, "start", interaction=inter, prize="x")
    assert "manage server" in sent.text.lower()
