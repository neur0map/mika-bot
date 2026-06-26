"""Social roleplay commands: registration, targeted and solo phrasing, fallback."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_member, tree_for

from mika.bot.commands import social


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(social.setup)


async def test_setup_registers_every_action(tree: app_commands.CommandTree[Any]) -> None:
    names = {cmd.name for cmd in tree.walk_commands() if isinstance(cmd, app_commands.Command)}
    expected = {action[0] for action in social._ACTIONS}
    assert expected <= names
    assert len(expected) == 24


async def test_hug_with_target_mentions_action_and_target(
    tree: app_commands.CommandTree[Any],
) -> None:
    sent = await invoke(tree, "hug", user=make_member(uid=99, name="alice"))
    assert sent
    text = sent.text.lower()
    assert "hug" in text
    assert "alice" in sent.text


async def test_hug_solo_when_no_user_given(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "hug")
    assert sent
    assert "hug" in sent.text.lower()
    assert "tester" in sent.text


async def test_kiss_targeted_includes_both_names(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "kiss", user=make_member(uid=77, name="bob"))
    assert "kiss" in sent.text.lower()
    assert "bob" in sent.text
    assert "tester" in sent.text


async def test_dance_targeted_phrasing(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "dance", user=make_member(uid=12, name="carol"))
    assert "danc" in sent.text.lower()
    assert "carol" in sent.text


async def test_handhold_apostrophe_template(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "handhold", user=make_member(uid=33, name="dave"))
    assert "dave" in sent.text
    assert "hand" in sent.text.lower()


async def test_yeet_solo(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "yeet")
    assert sent
    assert "yeet" in sent.text.lower()


async def test_every_action_sends_an_embed(tree: app_commands.CommandTree[Any]) -> None:
    for name, *_ in social._ACTIONS:
        sent = await invoke(tree, name)
        assert sent, f"{name} sent nothing"
        assert sent.text.strip(), f"{name} embed had no text"


async def test_targeted_uses_display_name_not_mention(
    tree: app_commands.CommandTree[Any],
) -> None:
    sent = await invoke(tree, "pat", user=make_member(uid=55, name="eve"))
    assert "eve" in sent.text
    assert "<@55>" not in sent.text
