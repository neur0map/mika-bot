"""Novelty commands: pure-logic exact checks plus mocked API smoke."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, make_member, tree_for

from mika.bot.commands import novelty


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(novelty.setup)


async def test_rps_valid_choice(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "rps", choice="rock")
    text = sent.text.lower()
    assert "rock" in text
    assert any(outcome in text for outcome in ("win", "lose", "tie"))


async def test_rps_invalid_choice(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "rps", choice="dynamite")
    text = sent.text.lower()
    assert "rock" in text
    assert "paper" in text
    assert "scissors" in text


async def test_iq_returns_a_number(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "iq", user=make_member(name="alice"))
    assert "alice" in sent.text
    digits = "".join(ch for ch in sent.text if ch.isdigit())
    assert digits, "expected an IQ score in the reply"
    assert 0 <= int(digits) <= 200


async def test_howgay_has_percent(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "howgay", user=make_member(name="bob"))
    assert "bob" in sent.text
    assert "%" in sent.text


async def test_rate_uses_ten_scale(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "rate", thing="pineapple pizza")
    assert "pineapple pizza" in sent.text
    assert "/10" in sent.text


async def test_wyr_offers_two_options(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "wyr")
    text = sent.text.lower()
    assert "would you rather" in text
    assert " or " in text


async def test_joke_sends_something(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "joke")
    assert sent


async def test_numberfact_sends_something(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "numberfact", number=42)
    assert sent
