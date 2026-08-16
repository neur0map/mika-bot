"""GIF search (Klipy, key-gated) and cobalt downloads."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import cobalt, gif


@pytest.fixture(scope="module")
def gif_tree() -> app_commands.CommandTree[Any]:
    return tree_for(gif.setup)


@pytest.fixture(scope="module")
def dl_tree() -> app_commands.CommandTree[Any]:
    return tree_for(cobalt.setup)


async def test_gif_without_key_denies(gif_tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(gif_tree, "gif", query="cat")
    assert "klipy" in sent.text.lower()


async def test_download_runs(dl_tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(dl_tree, "download", link="https://youtube.com/watch?v=x")
    assert sent


async def test_download_rejects_bad_link(dl_tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(dl_tree, "download", link="notalink")
    assert "link" in sent.text.lower()
