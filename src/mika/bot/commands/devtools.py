"""Developer utilities: JSON, text-case, encoding, regex and timestamp helpers."""

from __future__ import annotations

import binascii
import json
import re
import secrets
import urllib.parse
from datetime import UTC, datetime
from typing import Any

from discord import Interaction, app_commands

from mika.bot.commands import helpers

_LOREM_MIN = 1
_LOREM_MAX = 20
_LOREM_WORDS_MIN = 5
_LOREM_WORDS_MAX = 14
_REGEX_TEXT_CAP = 4000
_LOREM_POOL: tuple[str, ...] = (
    "lorem",
    "ipsum",
    "dolor",
    "sit",
    "amet",
    "consectetur",
    "adipiscing",
    "elit",
    "sed",
    "do",
    "eiusmod",
    "tempor",
    "incididunt",
    "ut",
    "labore",
    "et",
    "dolore",
    "magna",
    "aliqua",
    "enim",
    "ad",
    "minim",
    "veniam",
    "quis",
    "nostrud",
    "exercitation",
    "ullamco",
    "laboris",
    "nisi",
    "aliquip",
    "ex",
    "ea",
    "commodo",
    "consequat",
    "duis",
    "aute",
    "irure",
    "in",
    "reprehenderit",
    "voluptate",
    "velit",
    "esse",
    "cillum",
    "fugiat",
    "nulla",
    "pariatur",
    "excepteur",
    "sint",
    "occaecat",
    "cupidatat",
    "non",
    "proident",
    "sunt",
    "culpa",
    "qui",
    "officia",
    "deserunt",
    "mollit",
    "anim",
    "id",
    "est",
    "laborum",
)
_WORD_SPLIT = re.compile(r"[^A-Za-z0-9]+")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _words(text: str) -> list[str]:
    out: list[str] = []
    for chunk in _WORD_SPLIT.split(text):
        if chunk:
            out.extend(part for part in _CAMEL_BOUNDARY.split(chunk) if part)
    return out


def _slug(text: str) -> str:
    return "-".join(part.lower() for part in _words(text))


def _snake(text: str) -> str:
    return "_".join(part.lower() for part in _words(text))


def _kebab(text: str) -> str:
    return "-".join(part.lower() for part in _words(text))


def _camel(text: str) -> str:
    parts = _words(text)
    if not parts:
        return ""
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


def _lorem(sentences: int) -> str:
    count = max(_LOREM_MIN, min(sentences, _LOREM_MAX))
    span = _LOREM_WORDS_MAX - _LOREM_WORDS_MIN + 1
    out: list[str] = []
    for _ in range(count):
        length = _LOREM_WORDS_MIN + secrets.randbelow(span)
        chosen = [secrets.choice(_LOREM_POOL) for _ in range(length)]
        chosen[0] = chosen[0].capitalize()
        out.append(" ".join(chosen) + ".")
    return " ".join(out)


def _b64url_decode(segment: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    return binascii.a2b_base64(padded.replace("-", "+").replace("_", "/"))


def _decode_jwt(token: str) -> str:
    parts = token.strip().split(".")
    if len(parts) < 2:
        raise ValueError("expected header.payload.signature")
    header = json.loads(_b64url_decode(parts[0]).decode("utf-8", errors="replace"))
    payload = json.loads(_b64url_decode(parts[1]).decode("utf-8", errors="replace"))
    return json.dumps({"header": header, "payload": payload}, indent=2, ensure_ascii=False)


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register developer-utility commands on the tree."""

    @tree.command(name="jsonformat", description="Pretty-print a JSON document.")
    @app_commands.describe(data="JSON text to format")
    async def jsonformat(interaction: Interaction, data: str) -> None:
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as error:
            await helpers.send(interaction, f"invalid JSON: {error.msg}")
            return
        formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
        await helpers.send(interaction, helpers.clip(f"```json\n{formatted}\n```"))

    @tree.command(name="jsonmin", description="Minify a JSON document.")
    @app_commands.describe(data="JSON text to minify")
    async def jsonmin(interaction: Interaction, data: str) -> None:
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as error:
            await helpers.send(interaction, f"invalid JSON: {error.msg}")
            return
        minified = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
        await helpers.send(interaction, helpers.clip(f"`{minified}`"))

    @tree.command(name="slugify", description="Convert text into a URL-friendly slug.")
    @app_commands.describe(text="text to slugify")
    async def slugify(interaction: Interaction, text: str) -> None:
        await helpers.send(interaction, helpers.clip(f"`{_slug(text)}`"))

    @tree.command(name="lorem", description="Generate lorem ipsum filler text.")
    @app_commands.describe(sentences="sentence count (1-20, default 3)")
    async def lorem(interaction: Interaction, sentences: int = 3) -> None:
        await helpers.send(interaction, helpers.clip(_lorem(sentences)))

    @tree.command(name="wordcount", description="Count words, characters and lines in text.")
    @app_commands.describe(text="text to measure")
    async def wordcount(interaction: Interaction, text: str) -> None:
        words = len(text.split())
        chars = len(text)
        lines = len(text.splitlines()) if text else 0
        await helpers.send(interaction, f"{words} words, {chars} characters, {lines} lines")

    @tree.command(name="snakecase", description="Convert text to snake_case.")
    @app_commands.describe(text="text to convert")
    async def snakecase(interaction: Interaction, text: str) -> None:
        await helpers.send(interaction, helpers.clip(f"`{_snake(text)}`"))

    @tree.command(name="camelcase", description="Convert text to camelCase.")
    @app_commands.describe(text="text to convert")
    async def camelcase(interaction: Interaction, text: str) -> None:
        await helpers.send(interaction, helpers.clip(f"`{_camel(text)}`"))

    @tree.command(name="kebabcase", description="Convert text to kebab-case.")
    @app_commands.describe(text="text to convert")
    async def kebabcase(interaction: Interaction, text: str) -> None:
        await helpers.send(interaction, helpers.clip(f"`{_kebab(text)}`"))

    @tree.command(name="urlencode", description="Percent-encode text for use in a URL.")
    @app_commands.describe(text="text to encode")
    async def urlencode(interaction: Interaction, text: str) -> None:
        await helpers.send(interaction, helpers.clip(f"`{urllib.parse.quote(text, safe='')}`"))

    @tree.command(name="urldecode", description="Decode a percent-encoded string.")
    @app_commands.describe(text="text to decode")
    async def urldecode(interaction: Interaction, text: str) -> None:
        await helpers.send(interaction, helpers.clip(f"`{urllib.parse.unquote(text)}`"))

    @tree.command(name="timestamp", description="Render Discord timestamp tags from epoch or now.")
    @app_commands.describe(when="'now' or a unix epoch integer")
    async def timestamp(interaction: Interaction, when: str = "now") -> None:
        cleaned = when.strip().lower()
        if cleaned == "now":
            epoch = int(datetime.now(tz=UTC).timestamp())
        else:
            try:
                epoch = int(cleaned)
            except ValueError:
                await helpers.send(interaction, "give me 'now' or an integer epoch")
                return
        tags = " ".join(f"<t:{epoch}:{style}>" for style in ("F", "f", "D", "R"))
        await helpers.send(interaction, f"epoch `{epoch}`\n{tags}")

    @tree.command(name="jwtdecode", description="Decode a JWT header and payload (no verify).")
    @app_commands.describe(jwt="a JWT in header.payload.signature form")
    async def jwtdecode(interaction: Interaction, jwt: str) -> None:
        try:
            decoded = _decode_jwt(jwt)
        except (ValueError, binascii.Error) as error:
            await helpers.send(interaction, f"couldn't decode that token: {error}")
            return
        await helpers.send(interaction, helpers.clip(f"```json\n{decoded}\n```"))

    @tree.command(name="regextest", description="Test a regex against text and show matches.")
    @app_commands.describe(pattern="Python regex pattern", text="text to search")
    async def regextest(interaction: Interaction, pattern: str, text: str) -> None:
        body = text[:_REGEX_TEXT_CAP]
        try:
            compiled = re.compile(pattern)
        except re.error as error:
            await helpers.send(interaction, f"invalid pattern: {error}")
            return
        match = compiled.search(body)
        if match is None:
            await helpers.send(interaction, "no match")
            return
        lines = [f"match: `{match.group(0)}`"]
        for index, group in enumerate(match.groups(), start=1):
            lines.append(f"group {index}: `{group}`")
        await helpers.send(interaction, helpers.clip("\n".join(lines)))
