"""Ticket commands: gating, config persistence and channel guards."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import (
    invoke,
    make_channel,
    make_guild,
    make_interaction,
    make_member,
    make_role,
    tree_for,
)

from mika.bot.commands import tickets
from mika.persistence.repositories.config import get_setting


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(tickets.setup)


async def test_open_requires_guild(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "open", interaction=make_interaction(guild=None))
    assert "server" in sent.text.lower()


async def test_close_requires_ticket_channel(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "close")
    assert "ticket" in sent.text.lower()


async def test_setstaffrole_persists(tree: app_commands.CommandTree[Any]) -> None:
    guild = make_guild()
    guild.id = 301
    await invoke(tree, "setstaffrole", interaction=make_interaction(guild=guild), role=make_role())
    assert await get_setting(301, "ticket_staffrole") is not None


async def test_config_shows(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "config")
    assert "ticket" in sent.text.lower()


async def test_non_admin_denied(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction(user=make_member(admin=False))
    sent = await invoke(tree, "setcategory", interaction=inter, category=make_channel())
    assert "manage server" in sent.text.lower()
