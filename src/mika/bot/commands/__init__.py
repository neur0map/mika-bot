"""Slash commands. One file per category; register_all wires them to the tree."""

from __future__ import annotations

from typing import Any

from discord import app_commands

from mika.bot.commands import ai, basic, fun, images, info, text

__all__ = ["register_all"]


def register_all(tree: app_commands.CommandTree[Any]) -> None:
    """Attach every slash command to the command tree."""
    basic.setup(tree)
    fun.setup(tree)
    info.setup(tree)
    images.setup(tree)
    ai.setup(tree)
    text.setup(tree)
