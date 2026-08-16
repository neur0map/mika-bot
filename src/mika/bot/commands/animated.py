"""Animated message commands: a few bounded message edits for fun reveals."""

from __future__ import annotations

import asyncio
from typing import Any

from discord import Interaction, app_commands

_STEP = 0.8
_MAX_FRAMES = 8
_CLOCKS = ["\U0001f550", "\U0001f552", "\U0001f554", "\U0001f556", "\U0001f558", "\U0001f55a"]


def _countdown_frames(start: int) -> list[str]:
    start = max(1, min(10, start))
    nums = list(range(start, 0, -1))[: _MAX_FRAMES - 1]
    return [f"**{n}**" for n in nums] + ["\U0001f680 liftoff!"]


def _loading_frames() -> list[str]:
    bars = 10
    steps = [0, 2, 4, 6, 8, 10]
    out: list[str] = []
    for filled in steps:
        bar = "\u2588" * filled + "\u2591" * (bars - filled)
        pct = filled * 10
        out.append(f"`[{bar}]` {pct}%")
    out.append("done!")
    return out


def _typewriter_frames(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return ["..."]
    n = len(text)
    frames: list[str] = []
    for i in range(1, _MAX_FRAMES + 1):
        cut = max(1, (i * n) // _MAX_FRAMES)
        slice_ = text[:cut]
        if not frames or frames[-1] != slice_:
            frames.append(slice_)
    return frames


def _clock_frames() -> list[str]:
    return [*_CLOCKS, "\u23f0 ding!"]


def _bomb_frames() -> list[str]:
    return [
        "\U0001f4a3 \u22ef\u22ef\u22ef\u22ef\u22ef",
        "\U0001f4a3 \u22ef\u22ef\u22ef\u22ef",
        "\U0001f4a3 \u22ef\u22ef\u22ef",
        "\U0001f4a3 \u22ef\u22ef",
        "\U0001f4a3 \u22ef",
        "\U0001f4a5 boom!",
    ]


def _abc_frames() -> list[str]:
    letters = "abcdefghijklmnopqrstuvwxyz"
    cuts = [5, 10, 15, 20, 26]
    return [letters[:c] for c in cuts]


async def _play(interaction: Interaction, frames: list[str]) -> None:
    frames = frames[:_MAX_FRAMES]
    if not frames:
        return
    await interaction.response.send_message(frames[0])
    try:
        msg = await interaction.original_response()
        for frame in frames[1:]:
            await asyncio.sleep(_STEP)
            await msg.edit(content=frame)
    except Exception:
        return


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the animated-message commands."""

    @tree.command(name="countdown", description="Countdown from a number to liftoff.")
    async def countdown(interaction: Interaction, start: int = 5) -> None:
        await _play(interaction, _countdown_frames(start))

    @tree.command(name="loading", description="A short loading-bar animation.")
    async def loading(interaction: Interaction) -> None:
        await _play(interaction, _loading_frames())

    @tree.command(name="typewriter", description="Reveal text one piece at a time.")
    async def typewriter(interaction: Interaction, text: str) -> None:
        await _play(interaction, _typewriter_frames(text))

    @tree.command(name="clock", description="Spin through a few clock faces.")
    async def clock(interaction: Interaction) -> None:
        await _play(interaction, _clock_frames())

    @tree.command(name="bomb", description="Light a fuse and watch it blow.")
    async def bomb(interaction: Interaction) -> None:
        await _play(interaction, _bomb_frames())

    @tree.command(name="abc", description="Reveal the alphabet in chunks.")
    async def abc(interaction: Interaction) -> None:
        await _play(interaction, _abc_frames())
