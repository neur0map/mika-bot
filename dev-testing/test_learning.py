"""Self-reflection commands: run, recall and toggle the weekly loop."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_interaction, make_member, tree_for

from mika.bot.commands import learning


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(learning.setup)


async def test_reflect_runs(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "reflect")
    assert "reflection" in sent.text.lower()


async def test_recent_after_reflect(tree: app_commands.CommandTree[Any]) -> None:
    await invoke(tree, "reflect")
    sent = await invoke(tree, "recent")
    assert sent


async def test_auto_toggle(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "auto", on=True)
    assert "on" in sent.text.lower()


async def test_non_admin_reflect_denied(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction(user=make_member(admin=False))
    sent = await invoke(tree, "reflect", interaction=inter)
    assert "manage server" in sent.text.lower()
