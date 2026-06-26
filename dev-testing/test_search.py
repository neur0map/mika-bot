"""Search registry/web commands run and reply."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import search


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(search.setup)


async def test_github(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "github", user="octocat")
    assert sent


async def test_npm(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "npm", package="express")
    assert sent


async def test_pypi(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "pypi", package="httpx")
    assert sent


async def test_xkcd_default(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "xkcd")
    assert sent


async def test_hackernews(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "hackernews")
    assert sent


async def test_country(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "country", name="japan")
    assert sent
