"""OSINT slash commands run offline via the harness with mocked HTTP."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import osint


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(osint.setup)


async def test_sherlock(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "sherlock", username="octocat")
    assert sent


async def test_dns(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "dns", domain="example.com")
    assert sent


async def test_useragent_detects_chrome(tree: app_commands.CommandTree[Any]) -> None:
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"
    sent = await invoke(tree, "useragent", ua=ua)
    text = sent.text
    assert "Chrome" in text
    assert "Windows" in text


async def test_emailcheck_valid(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "emailcheck", email="a@b.com")
    text = sent.text
    assert "yes" in text
    assert "b.com" in text


async def test_emailcheck_invalid(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "emailcheck", email="nope")
    text = sent.text
    assert "no" in text
