"""Conversion commands: registration, exact maths for pure logic, mocked currency."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import convert


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(convert.setup)


async def test_setup_registers_expected_commands(tree: app_commands.CommandTree[Any]) -> None:
    names = {cmd.name for cmd in tree.walk_commands() if isinstance(cmd, app_commands.Command)}
    expected = {
        "temperature",
        "length",
        "weight",
        "roman",
        "fromroman",
        "bytesize",
        "timezone",
        "speed",
        "currency",
    }
    assert expected <= names


async def test_temperature_c_to_f_is_212(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "temperature", value=100.0, from_unit="c", to_unit="f")
    assert "212" in sent.text


async def test_length_km_to_m_is_1000(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "length", value=1.0, from_unit="km", to_unit="m")
    assert "1000" in sent.text


async def test_weight_kg_to_g_is_1000(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "weight", value=1.0, from_unit="kg", to_unit="g")
    assert "1000" in sent.text


async def test_roman_nine_is_ix(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "roman", number=9)
    assert "IX" in sent.text


async def test_fromroman_iv_is_four(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "fromroman", numeral="IV")
    assert "4" in sent.text


async def test_fromroman_rejects_garbage(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "fromroman", numeral="ZZZ")
    assert "valid" in sent.text.lower()


async def test_currency_runs_with_mock(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "currency", amount=100.0, from_cur="USD", to_cur="EUR")
    assert sent
    assert "USD" in sent.text
