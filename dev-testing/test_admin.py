"""Admin utilities: emoji cloning and server templates."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_interaction, make_member, tree_for

from mika.bot.commands import admin


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(admin.setup)


async def test_steal_creates_emoji(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction()
    await invoke(tree, "steal", interaction=inter, name="kek", source="<:kek:12345>")
    inter.guild.create_custom_emoji.assert_awaited_once()


async def test_steal_rejects_garbage(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction()
    sent = await invoke(tree, "steal", interaction=inter, name="x", source="not-an-emoji")
    assert "emoji" in sent.text.lower()
    inter.guild.create_custom_emoji.assert_not_awaited()


async def test_template_creates_channels(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction()
    sent = await invoke(tree, "template", interaction=inter, preset="community")
    assert inter.guild.create_text_channel.await_count == 6
    assert "community" in sent.text


async def test_template_unknown_preset(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "template", preset="nonsense")
    assert "unknown" in sent.text.lower()


async def test_non_admin_denied(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction(user=make_member(admin=False))
    sent = await invoke(tree, "addchannel", interaction=inter, name="secret")
    assert "permission" in sent.text.lower()


async def test_presets_lists(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "presets")
    assert "community" in sent.text and "gaming" in sent.text
