"""Animated-message commands: the first frame lands, edits stay bounded."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import animated


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(animated.setup)


async def test_countdown_sends_first_frame(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "countdown", start=3)
    assert sent
    assert "3" in sent.text


async def test_countdown_clamps_huge_start(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "countdown", start=99)
    assert sent
    assert "10" in sent.text


async def test_typewriter_first_slice(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "typewriter", text="hello")
    assert sent
    assert sent.text.strip().startswith("h")


async def test_typewriter_blank_is_handled(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "typewriter", text="   ")
    assert sent
    assert "..." in sent.text


async def test_loading_sends_a_bar(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "loading")
    assert sent
    assert "%" in sent.text


async def test_clock_sends_something(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "clock")
    assert sent


async def test_bomb_sends_something(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "bomb")
    assert sent


async def test_abc_sends_first_chunk(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "abc")
    assert sent
    assert sent.text.strip().startswith("a")
