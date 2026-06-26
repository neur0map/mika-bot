"""Personality preset commands: list, preview, switch (keeps memory)."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_interaction, make_member, tree_for

from mika.bot.commands import persona


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(persona.setup)


async def test_list_shows_presets(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "list")
    assert "friendly" in sent.text.lower()


async def test_preview_known(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "preview", name="professional")
    assert "identity" in sent.text.lower()


async def test_preview_unknown(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "preview", name="nonsense")
    assert "unknown" in sent.text.lower()


async def test_set_then_current(tree: app_commands.CommandTree[Any]) -> None:
    await invoke(tree, "set", name="gamer")
    sent = await invoke(tree, "current")
    assert "gaming" in sent.text.lower()


async def test_non_admin_set_denied(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction(user=make_member(admin=False))
    sent = await invoke(tree, "set", interaction=inter, name="friendly")
    assert "manage server" in sent.text.lower()


async def test_create_generates(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "create", name="Robo", description="a sci-fi robot")
    assert "robo" in sent.text.lower()
