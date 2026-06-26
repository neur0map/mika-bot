"""Color palette commands behave as expected offline."""

from __future__ import annotations

import io
from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for
from PIL import Image

from mika.bot.commands import palette


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(palette.setup)


async def test_hex2rgb_decodes(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "hex2rgb", hex_code="#ff0000")
    assert "R=255" in sent.text
    assert "G=0" in sent.text and "B=0" in sent.text


async def test_rgb2hex_encodes(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "rgb2hex", r=0, g=255, b=0)
    assert "00ff00" in sent.text


async def test_name2hex_known(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "name2hex", name="red")
    assert "ff0000" in sent.text


async def test_complementary_inverts_black(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "complementary", hex_code="#000000")
    assert "ffffff" in sent.text


async def test_bad_hex_is_denied(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "hex2rgb", hex_code="not-a-hex")
    assert sent
    assert "RRGGBB" in sent.text


async def test_swatch_returns_png(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "swatch", hex_code="#123456")
    assert sent.file is not None
    sent.file.fp.seek(0)
    Image.open(io.BytesIO(sent.file.fp.read())).verify()


async def test_gradient_returns_png(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "gradient", start="#ff0000", end="#0000ff")
    assert sent.file is not None
    sent.file.fp.seek(0)
    Image.open(io.BytesIO(sent.file.fp.read())).verify()


async def test_setup_registers_nine_commands(tree: app_commands.CommandTree[Any]) -> None:
    names = {cmd.name for cmd in tree.walk_commands()}
    assert names == {
        "hex2rgb",
        "rgb2hex",
        "colorinfo",
        "complementary",
        "shades",
        "palette",
        "swatch",
        "gradient",
        "name2hex",
    }
