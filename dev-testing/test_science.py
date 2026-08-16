"""Math/science commands: exact-output checks for pure logic."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import science


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(science.setup)


async def test_isprime_true(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "isprime", number=7)
    text = sent.text
    assert "prime" in text
    assert "not prime" not in text


async def test_isprime_false(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "isprime", number=8)
    assert "not prime" in sent.text


async def test_factorial_five_is_120(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "factorial", number=5)
    assert "120" in sent.text


async def test_fibonacci_ten_is_55(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "fibonacci", n=10)
    assert "55" in sent.text


async def test_gcd_twelve_eight_is_four(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "gcd", a=12, b=8)
    assert "= 4" in sent.text


async def test_stats_basic_mean(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "stats", numbers="1,2,3,4")
    assert "2.5" in sent.text


async def test_quadratic_real_roots(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "quadratic", a=1.0, b=-3.0, c=2.0)
    text = sent.text
    assert "= 2" in text
    assert "= 1" in text


async def test_stats_bad_input_handled(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "stats", numbers="not numbers at all")
    assert "number" in sent.text.lower()
