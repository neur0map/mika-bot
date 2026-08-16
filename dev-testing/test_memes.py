"""Avatar effects and meme/ship commands."""

from __future__ import annotations

import io
import re
from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_member, tree_for
from PIL import Image

from mika.bot.commands import memes


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(memes.setup)


async def test_grayscale_returns_png(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "grayscale", user=make_member())
    assert sent.file is not None
    sent.file.fp.seek(0)
    Image.open(io.BytesIO(sent.file.fp.read())).verify()


async def test_every_effect_attaches_file(tree: app_commands.CommandTree[Any]) -> None:
    names = [name for name, _desc, _fn in memes._EFFECTS]
    user = make_member()
    for name in names:
        sent = await invoke(tree, name, user=user)
        assert sent.file is not None, name


async def test_effect_defaults_to_caller(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "invert")
    assert sent.file is not None


async def test_ship_shows_percentage(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(
        tree, "ship", user1=make_member(uid=1, name="alice"), user2=make_member(uid=2, name="bob")
    )
    assert re.search(r"\d{1,3}\s*%", sent.text)
    assert "alice" in sent.text and "bob" in sent.text


async def test_ship_is_deterministic(tree: app_commands.CommandTree[Any]) -> None:
    a, b = make_member(uid=11, name="a"), make_member(uid=22, name="b")
    first = await invoke(tree, "ship", user1=a, user2=b)
    second = await invoke(tree, "ship", user1=a, user2=b)
    assert first.text == second.text


async def test_ship_is_symmetric(tree: app_commands.CommandTree[Any]) -> None:
    a, b = make_member(uid=11, name="a"), make_member(uid=22, name="b")
    forward = await invoke(tree, "ship", user1=a, user2=b)
    reverse = await invoke(tree, "ship", user1=b, user2=a)
    forward_pct = re.search(r"(\d{1,3})\s*%", forward.text)
    reverse_pct = re.search(r"(\d{1,3})\s*%", reverse.text)
    assert forward_pct and reverse_pct
    assert forward_pct.group(1) == reverse_pct.group(1)


async def test_meme_runs(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "meme")
    assert sent


async def test_setup_registers_expected_count(tree: app_commands.CommandTree[Any]) -> None:
    names = {cmd.name for cmd in tree.walk_commands()}
    assert "meme" in names and "ship" in names
    assert {"grayscale", "deepfry", "wasted", "jail", "pride"} <= names
    assert len(names) == len(memes._EFFECTS) + 2
