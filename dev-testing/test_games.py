"""Game commands: dice, guesses, slots, scramble, mocked APIs."""

from __future__ import annotations

import re
from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import games


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(games.setup)


async def test_setup_registers_expected_commands(tree: app_commands.CommandTree[Any]) -> None:
    names = {cmd.name for cmd in tree.walk_commands() if isinstance(cmd, app_commands.Command)}
    expected = {
        "trivia",
        "roll",
        "guess",
        "slots",
        "scramble",
        "riddle",
        "truthordare",
        "neverhaveiever",
        "wouldyourather",
        "lottery",
        "coinduel",
    }
    assert expected <= names


async def test_roll_2d6_shows_total_and_rolls(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "roll", dice="2d6")
    assert sent
    text = sent.text
    assert "2d6" in text
    nums = [int(n) for n in re.findall(r"\d+", text)]
    rolls = [n for n in nums if 1 <= n <= 6]
    assert len(rolls) >= 2
    assert any(n >= 2 for n in nums)


async def test_roll_clamps_huge_count(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "roll", dice="9999d6")
    assert "20d6" in sent.text


async def test_roll_rejects_garbage(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "roll", dice="not a die")
    assert "couldn't" in sent.text.lower() or "try" in sent.text.lower()


async def test_guess_responds(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "guess", guess=5)
    assert sent
    assert "5" in sent.text
    text = sent.text.lower()
    assert any(word in text for word in ("nailed", "nope", "guessed"))


async def test_slots_responds(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "slots")
    assert sent
    assert "|" in sent.text
    assert sent.text.count("|") >= 2


async def test_scramble_answer_hidden_in_spoiler(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "scramble")
    assert sent.text.count("||") >= 2
    spoiler = re.search(r"\|\|(\w+)\|\|", sent.text)
    assert spoiler is not None
    assert spoiler.group(1) in games._SCRAMBLE_WORDS


async def test_trivia_mocked_runs(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "trivia")
    assert sent
    assert "||" in sent.text


async def test_riddle_mocked_runs(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "riddle")
    assert sent
    assert "||" in sent.text


async def test_truthordare_truth_then_dare(tree: app_commands.CommandTree[Any]) -> None:
    truth = await invoke(tree, "truthordare", mode="truth")
    assert "truth" in truth.text.lower()
    dare = await invoke(tree, "truthordare", mode="dare")
    assert "dare" in dare.text.lower()


async def test_truthordare_invalid_mode(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "truthordare", mode="banana")
    assert "truth" in sent.text.lower()
    assert "dare" in sent.text.lower()


async def test_wouldyourather_offers_two_options(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "wouldyourather")
    text = sent.text.lower()
    assert "would you rather" in text
    assert " or " in text


async def test_neverhaveiever_runs(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "neverhaveiever")
    assert "never have i ever" in sent.text.lower()


async def test_lottery_six_unique_numbers_in_range(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "lottery")
    nums = [int(n) for n in re.findall(r"\d+", sent.text)]
    assert len(nums) == 6
    assert all(1 <= n <= 49 for n in nums)
    assert len(set(nums)) == 6


async def test_coinduel_names_both_sides_and_a_winner(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "coinduel", side_a="alpha", side_b="bravo")
    text = sent.text.lower()
    assert "alpha" in text
    assert "bravo" in text
    assert "winner" in text
