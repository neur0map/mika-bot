"""Date and time commands: registration plus exact maths for pure local logic."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import timezones


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(timezones.setup)


async def test_setup_registers_expected_commands(tree: app_commands.CommandTree[Any]) -> None:
    names = {cmd.name for cmd in tree.walk_commands() if isinstance(cmd, app_commands.Command)}
    expected = {
        "timein",
        "worldclock",
        "unixnow",
        "fromunix",
        "age",
        "daysbetween",
        "weekday",
        "countdown",
        "timestamp",
    }
    assert expected <= names


async def test_timein_utc_runs(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "timein", zone="UTC")
    assert "UTC" in sent.text


async def test_age_shows_number(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "age", birthdate="2000-01-01")
    assert any(ch.isdigit() for ch in sent.text)


async def test_daysbetween_one_week_is_seven(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "daysbetween", start="2020-01-01", end="2020-01-08")
    assert "7" in sent.text


async def test_weekday_jan_one_2020_is_wednesday(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "weekday", date="2020-01-01")
    assert "Wednesday" in sent.text


async def test_bad_date_is_rejected(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "weekday", date="not-a-date")
    assert "YYYY" in sent.text
