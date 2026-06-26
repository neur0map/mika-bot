"""Developer-utility commands: pure-logic transforms and graceful failure paths."""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest
from discord import app_commands
from harness import invoke, tree_for

from mika.bot.commands import devtools


@pytest.fixture(scope="module")
def tree() -> app_commands.CommandTree[Any]:
    return tree_for(devtools.setup)


async def test_setup_registers_all_commands(tree: app_commands.CommandTree[Any]) -> None:
    names = {cmd.name for cmd in tree.walk_commands() if isinstance(cmd, app_commands.Command)}
    expected = {
        "jsonformat",
        "jsonmin",
        "slugify",
        "lorem",
        "wordcount",
        "snakecase",
        "camelcase",
        "kebabcase",
        "urlencode",
        "urldecode",
        "timestamp",
        "jwtdecode",
        "regextest",
    }
    assert expected <= names
    assert len(expected) == 13


async def test_slugify_lowercases_and_hyphenates(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "slugify", text="Hello World!")
    assert "hello-world" in sent.text


async def test_jsonformat_pretty_prints(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "jsonformat", data='{"a":1}')
    assert '"a"' in sent.text
    assert "```json" in sent.text


async def test_jsonformat_rejects_invalid(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "jsonformat", data="not json")
    assert "invalid" in sent.text.lower()


async def test_snakecase_converts_camel(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "snakecase", text="helloWorld")
    assert "hello_world" in sent.text


async def test_jwtdecode_handles_sample_token(tree: app_commands.CommandTree[Any]) -> None:
    def encode(obj: dict[str, Any]) -> str:
        raw = json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    token = f"{encode({'alg': 'HS256', 'typ': 'JWT'})}.{encode({'sub': 'abc'})}.signature"
    sent = await invoke(tree, "jwtdecode", jwt=token)
    assert "HS256" in sent.text
    assert "abc" in sent.text


async def test_jwtdecode_handles_malformed(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "jwtdecode", jwt="garbage")
    assert sent
    assert "decode" in sent.text.lower() or "expected" in sent.text.lower()


async def test_regextest_handles_bad_pattern(tree: app_commands.CommandTree[Any]) -> None:
    sent = await invoke(tree, "regextest", pattern="(unclosed", text="anything")
    assert sent
    assert "invalid" in sent.text.lower()
