"""Public crypto market-data commands run and reply."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import finance


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(finance.setup)


async def test_cryptoprice(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "cryptoprice", coin="bitcoin")
    assert sent


async def test_trending(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "trending")
    assert sent


async def test_feargreed(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "feargreed")
    assert sent


async def test_cryptoconvert(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "cryptoconvert", amount=2.0, coin="bitcoin")
    assert sent


async def test_topcoins(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "topcoins")
    assert sent


async def test_marketcap(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "marketcap", coin="ethereum")
    assert sent
