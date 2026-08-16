"""Smoke: every registered slash command runs headlessly without raising."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import build_tree, invoke, synth_kwargs

# Commands that genuinely need a live gateway and can't run against fakes.
SKIP: set[str] = set()


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return build_tree()


async def test_every_command_runs(tree: app_commands.CommandTree[Any]) -> None:
    failures: list[str] = []
    total = 0
    for cmd in tree.walk_commands():
        if not isinstance(cmd, app_commands.Command):
            continue
        total += 1
        if cmd.qualified_name in SKIP:
            continue
        try:
            sent = await invoke(tree, cmd.qualified_name, **synth_kwargs(cmd))
        except Exception as error:
            failures.append(f"{cmd.qualified_name}: {type(error).__name__}: {error}")
            continue
        if not sent:
            failures.append(f"{cmd.qualified_name}: sent nothing")
    assert not failures, "command failures:\n" + "\n".join(failures)
    assert total >= 1


def test_command_count(tree: app_commands.CommandTree[Any]) -> None:
    commands = [c for c in tree.walk_commands() if isinstance(c, app_commands.Command)]
    print(f"\nregistered slash commands: {len(commands)}")
    assert len(commands) >= 1
