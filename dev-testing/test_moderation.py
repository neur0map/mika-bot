"""Moderation commands: permission gating and action dispatch."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_interaction, make_member, make_role, tree_for

from mika.bot.commands import moderation


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(moderation.setup)


async def test_kick_calls_kick(tree: app_commands.CommandTree[Any]) -> None:
    target = make_member(uid=99, name="victim")
    sent = await invoke(tree, "kick", user=target)
    target.kick.assert_awaited_once()
    assert "victim" in sent.text


async def test_ban_calls_ban(tree: app_commands.CommandTree[Any]) -> None:
    target = make_member(uid=5, name="baddie")
    await invoke(tree, "ban", user=target)
    target.ban.assert_awaited_once()


async def test_non_admin_is_denied(tree: app_commands.CommandTree[Any]) -> None:
    caller = make_member(admin=False)
    target = make_member(uid=7)
    inter = make_interaction(user=caller)
    sent = await invoke(tree, "kick", interaction=inter, user=target)
    target.kick.assert_not_awaited()
    assert "permission" in sent.text.lower()


async def test_guild_only(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction(guild=None)
    sent = await invoke(tree, "createrole", interaction=inter, name="newrole")
    assert "server" in sent.text.lower()


async def test_unban_bad_id(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "unban", user_id="not-a-number")
    assert "valid" in sent.text.lower()


async def test_addrole_dispatches(tree: app_commands.CommandTree[Any]) -> None:
    target = make_member(uid=11)
    await invoke(tree, "addrole", user=target, role=make_role())
    target.add_roles.assert_awaited_once()
