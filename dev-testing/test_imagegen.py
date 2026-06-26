"""Image generation commands attach a file to their reply."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import imagegen


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(imagegen.setup)


async def test_imagine(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "imagine", prompt="a cat")
    assert sent.file is not None


async def test_imagine_with_seed(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "imagine", prompt="a cat in space", seed=42)
    assert sent.file is not None


async def test_imaginewide(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "imaginewide", prompt="x")
    assert sent.file is not None


async def test_imaginetall(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "imaginetall", prompt="a tall tower")
    assert sent.file is not None


async def test_imaginesquare(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "imaginesquare", prompt="a square")
    assert sent.file is not None


async def test_avatarart(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "avatarart", prompt="a fox")
    assert sent.file is not None
