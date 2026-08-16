"""Generator/utility commands: arithmetic safety, password length, qr files."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import tools


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(tools.setup)


async def test_calc_basic(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "calc", expression="2+2*3")
    assert "8" in sent.text


async def test_calc_rejects_import(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "calc", expression='__import__("os")')
    text = sent.text.lower()
    assert "can't" in text or "not allowed" in text or "couldn't" in text


async def test_calc_rejects_attribute_access(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "calc", expression="(1).bit_length")
    assert sent
    assert "bit_length" not in sent.text


async def test_passgen_length(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "passgen", length=20)
    body = sent.text.replace("`", "").strip()
    assert len(body) == 20


async def test_passgen_clamps(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "passgen", length=1)
    body = sent.text.replace("`", "").strip()
    assert len(body) == 4


async def test_hash_sha256_matches_hashlib(tree: app_commands.CommandTree[Any]) -> None:
    expected = hashlib.sha256(b"abc").hexdigest()
    sent = await invoke(tree, "hash", text="abc", algorithm="sha256")
    assert expected in sent.text


async def test_hash_rejects_unknown_algo(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "hash", text="abc", algorithm="bogus")
    assert "supported" in sent.text.lower()


async def test_qrcode_attaches_file(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "qrcode", text="hi")
    assert sent.file is not None


async def test_uuid_format(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "uuid")
    body = sent.text.replace("`", "").strip()
    assert len(body) == 36
    assert body.count("-") == 4


async def test_base_conversion(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "base", number="255", from_base=10, to_base=16)
    assert "ff" in sent.text.lower()


async def test_base_rejects_invalid_base(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "base", number="10", from_base=1, to_base=2)
    assert "couldn't" in sent.text.lower()


async def test_strlen_counts(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "strlen", text="hello world")
    assert "11 characters" in sent.text
    assert "2 words" in sent.text


async def test_randomcolor_embed(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "randomcolor")
    assert "#" in sent.text


async def test_tinyurl_returns_response(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "tinyurl", url="https://example.com")
    assert sent


async def test_iplookup_runs(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "iplookup", ip="8.8.8.8")
    assert sent


async def test_usergen_runs(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "usergen")
    assert sent


async def test_domain_runs(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "domain", domain="example.com")
    assert sent


def test_setup_registers_expected_commands() -> None:
    tree = tree_for(tools.setup)
    names = {cmd.name for cmd in tree.walk_commands()}
    expected = {
        "qrcode",
        "passgen",
        "hash",
        "uuid",
        "calc",
        "randomcolor",
        "base",
        "strlen",
        "tinyurl",
        "iplookup",
        "usergen",
        "domain",
    }
    assert expected.issubset(names)
