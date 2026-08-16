"""Welcome/goodbye/autorole config commands and the join handler."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_guild, make_interaction, make_member, make_role, tree_for

from mika.bot.commands import welcome
from mika.bot.greetings import handle_member_join
from mika.persistence.repositories.config import get_setting


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(welcome.setup)


async def test_welcomemessage_persists(tree: app_commands.CommandTree[Any]) -> None:
    guild = make_guild()
    guild.id = 101
    inter = make_interaction(guild=guild)
    await invoke(tree, "welcomemessage", interaction=inter, message="hi {user}")
    assert await get_setting(101, "welcome_message") == "hi {user}"


async def test_welcometest_renders(tree: app_commands.CommandTree[Any]) -> None:
    guild = make_guild()
    guild.id = 102
    inter = make_interaction(guild=guild)
    await invoke(tree, "welcomemessage", interaction=inter, message="yo {user} at {server}")
    sent = await invoke(tree, "welcometest", interaction=inter)
    assert inter.user.mention in sent.text


async def test_non_admin_denied(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction(user=make_member(admin=False))
    sent = await invoke(tree, "autorole", interaction=inter, role=make_role())
    assert "manage server" in sent.text.lower()


async def test_autorole_then_join_assigns(tree: app_commands.CommandTree[Any]) -> None:
    guild = make_guild()
    guild.id = 103
    role = make_role()
    guild.get_role = lambda _rid: role
    inter = make_interaction(guild=guild)
    await invoke(tree, "autorole", interaction=inter, role=role)
    member = make_member()
    member.guild = guild
    await handle_member_join(member)
    member.add_roles.assert_awaited()
