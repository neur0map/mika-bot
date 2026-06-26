"""Quotes/jokes commands: mocked API smoke plus pure-logic checks."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_member, tree_for

from mika.bot.commands import quotes


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(quotes.setup)


async def test_quote_sends_something(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "quote")
    assert sent


async def test_chucknorris_sends_something(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "chucknorris")
    assert sent


async def test_motivate_sends_something(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "motivate")
    assert sent


async def test_fortune_returns_text(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "fortune")
    assert sent.text.strip()


async def test_pickup_returns_text(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "pickup")
    assert sent.text.strip()


async def test_wisdom_returns_text(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "wisdom")
    assert sent.text.strip()


async def test_roast_mentions_user(tree: app_commands.CommandTree[Any]) -> None:
    member = make_member(uid=99, name="victim")
    sent = await invoke(tree, "roast", user=member)
    assert "<@99>" in sent.text
