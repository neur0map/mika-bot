"""Anti-spam config commands and the content-filter detection logic."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_guild, make_interaction, make_member, tree_for

from mika.bot.antispam import check
from mika.bot.commands import antispam
from mika.persistence.repositories.config import get_setting


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(antispam.setup)


async def test_enable_persists(tree: app_commands.CommandTree[Any]) -> None:
    guild = make_guild()
    guild.id = 201
    inter = make_interaction(guild=guild)
    await invoke(tree, "enable", interaction=inter)
    assert await get_setting(201, "antispam_enabled") == "1"


async def test_invites_toggle(tree: app_commands.CommandTree[Any]) -> None:
    guild = make_guild()
    guild.id = 202
    inter = make_interaction(guild=guild)
    await invoke(tree, "invites", interaction=inter, on=True)
    assert await get_setting(202, "filter_invites") == "1"


async def test_non_admin_denied(tree: app_commands.CommandTree[Any]) -> None:
    inter = make_interaction(user=make_member(admin=False))
    sent = await invoke(tree, "enable", interaction=inter)
    assert "manage server" in sent.text.lower()


def _message(content: str = "", mentions: list[Any] | None = None) -> Any:
    return SimpleNamespace(
        content=content,
        mentions=mentions or [],
        guild=SimpleNamespace(id=1),
        author=SimpleNamespace(id=2, bot=False),
    )


def test_check_blocks_invite() -> None:
    assert check(_message("join discord.gg/abc"), {"filter_invites": "1"}) is not None


def test_check_allows_clean() -> None:
    config = {"filter_invites": "1", "filter_links": "1"}
    assert check(_message("hello there friends"), config) is None


def test_check_blocks_mass_mentions() -> None:
    assert check(_message("hi", mentions=[1, 2, 3, 4]), {"max_mentions": "2"}) is not None
