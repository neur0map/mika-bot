"""Text-transform commands: exact round-trip and output checks."""

from __future__ import annotations

from typing import Any

import pytest
from discord import app_commands
from harness import build_tree, invoke


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return build_tree()


async def test_reverse(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "reverse", text="hello")
    assert "olleh" in sent.text


async def test_base64_roundtrip(tree: app_commands.CommandTree[Any]) -> None:
    enc = await invoke(tree, "encode", text="hello world")
    dec = await invoke(tree, "decode", text=enc.text.strip())
    assert "hello world" in dec.text


async def test_rot13_symmetric(tree: app_commands.CommandTree[Any]) -> None:
    enc = await invoke(tree, "encrypt", text="Hello")
    assert enc.text.strip() == "Uryyb"
    dec = await invoke(tree, "decrypt", text="Uryyb")
    assert "Hello" in dec.text


async def test_binary_roundtrip(tree: app_commands.CommandTree[Any]) -> None:
    encoded = await invoke(tree, "text2bin", text="hi")
    decoded = await invoke(tree, "bin2text", text=encoded.text.strip())
    assert "hi" in decoded.text


async def test_hex_roundtrip(tree: app_commands.CommandTree[Any]) -> None:
    encoded = await invoke(tree, "text2hex", text="hi")
    decoded = await invoke(tree, "hex2text", text=encoded.text.strip())
    assert "hi" in decoded.text


async def test_morse(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "morse", text="sos")
    assert "... --- ..." in sent.text


async def test_smart_case(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "smart", text="abcd")
    assert sent.text.strip() == "aBcD"


async def test_ascii_is_codeblock(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "ascii", text="hi")
    assert "```" in sent.text


async def test_bad_base64_is_handled(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "decode", text="!!!not base64!!!")
    assert "couldn't" in sent.text.lower()
