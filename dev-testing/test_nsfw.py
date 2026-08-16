"""Age-gated image commands: channel gate + happy path."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_channel, make_interaction, tree_for

from mika.bot.commands import nsfw

_NAMES = ["nsfwwaifu", "hentai", "milf", "oral", "ero", "ass"]


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(nsfw.setup)


def test_registers_expected_commands(tree: app_commands.CommandTree[Any]) -> None:
    names = {cmd.name for cmd in tree.walk_commands()}
    for expected in _NAMES:
        assert expected in names
    assert len(names) >= 6


async def test_blocks_outside_age_gate(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "hentai")
    assert "age" in sent.text.lower()


async def test_blocks_every_command_outside_age_gate(
    tree: app_commands.CommandTree[Any],
) -> None:
    for name in _NAMES:
        sent = await invoke(tree, name)
        assert "age" in sent.text.lower(), f"{name} did not deny"


async def test_returns_image_inside_age_gate(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction(channel=make_channel(nsfw=True))
    sent = await invoke(tree, "nsfwwaifu", interaction=inter)
    assert sent


async def test_each_command_replies_inside_age_gate(
    tree: app_commands.CommandTree[Any],
) -> None:
    for name in _NAMES:
        inter = make_interaction(channel=make_channel(nsfw=True))
        sent = await invoke(tree, name, interaction=inter)
        assert sent, f"{name} produced no reply"


async def test_fetch_failure_sends_fallback(
    tree: app_commands.CommandTree[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("offline")

    from mika.bot.commands import helpers

    monkeypatch.setattr(helpers, "fetch_json", boom)
    inter = make_interaction(channel=make_channel(nsfw=True))
    sent = await invoke(tree, "milf", interaction=inter)
    assert "couldn't" in sent.text.lower()
