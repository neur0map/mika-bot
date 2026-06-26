"""Word/language commands run and produce sensible output."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import words


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(words.setup)


async def test_synonyms_runs(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "synonyms", word="happy")
    assert sent


async def test_anagram_true(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "anagram", first="listen", second="silent")
    assert "are anagrams" in sent.text
    assert "not anagrams" not in sent.text


async def test_anagram_false(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "anagram", first="a", second="b")
    assert "not anagrams" in sent.text


async def test_scrabble_score(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "scrabble", word="quiz")
    assert "22" in sent.text


async def test_syllables_banana(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "syllables", word="banana")
    assert "3" in sent.text
