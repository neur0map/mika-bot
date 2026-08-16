"""Generator and utility commands: qr codes, passwords, hashes, calc, lookups."""

from __future__ import annotations

import ast
import hashlib
import io
import secrets
import string
import urllib.parse
import uuid
from typing import Any

import discord
import qrcode
from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_PWD_MIN = 4
_PWD_MAX = 128
_PWD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
_HASH_ALGOS = {"md5", "sha1", "sha256", "sha512"}
_QR_LIMIT = 1024
_TEXT_LIMIT = 2000
_BASE_MIN = 2
_BASE_MAX = 36
_BASE_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
_POW_LIMIT = 100


def _eval_node(node: ast.AST) -> Any:
    match node:
        case ast.Constant(value=v) if isinstance(v, int | float) and not isinstance(v, bool):
            return v
        case ast.UnaryOp(op=ast.UAdd(), operand=x):
            return +_eval_node(x)
        case ast.UnaryOp(op=ast.USub(), operand=x):
            return -_eval_node(x)
        case ast.BinOp(left=lhs, op=op, right=rhs):
            left, right = _eval_node(lhs), _eval_node(rhs)
            if isinstance(op, ast.Add):
                return left + right
            if isinstance(op, ast.Sub):
                return left - right
            if isinstance(op, ast.Mult):
                return left * right
            if isinstance(op, ast.Div):
                return left / right
            if isinstance(op, ast.Mod):
                return left % right
            if isinstance(op, ast.Pow):
                if abs(right) > _POW_LIMIT or abs(left) > 10**6:
                    raise ValueError("number too large")
                return left**right
            raise ValueError("operator not allowed")
        case _:
            raise ValueError("expression not allowed")


def _safe_calc(expression: str) -> Any:
    tree = ast.parse(expression, mode="eval")
    result = _eval_node(tree.body)
    if isinstance(result, float) and result.is_integer():
        return int(result)
    return result


def _convert_base(number: str, from_base: int, to_base: int) -> str:
    if not (_BASE_MIN <= from_base <= _BASE_MAX and _BASE_MIN <= to_base <= _BASE_MAX):
        raise ValueError("base must be between 2 and 36")
    value = int(number.strip(), from_base)
    if value == 0:
        return "0"
    negative = value < 0
    value = abs(value)
    out: list[str] = []
    while value:
        out.append(_BASE_DIGITS[value % to_base])
        value //= to_base
    return ("-" if negative else "") + "".join(reversed(out))


def _build_qr(text: str) -> io.BytesIO:
    img = qrcode.make(text[:_QR_LIMIT])
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _random_password(length: int) -> str:
    length = max(_PWD_MIN, min(length, _PWD_MAX))
    return "".join(secrets.choice(_PWD_ALPHABET) for _ in range(length))


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register generator and utility commands on the tree."""

    @tree.command(name="qrcode", description="Generate a QR code image from text.")
    @app_commands.describe(text="text or URL to encode")
    async def qrcode_cmd(interaction: Interaction, text: str) -> None:
        if not text.strip():
            await helpers.deny(interaction, "give me something to encode")
            return
        try:
            buffer = _build_qr(text)
        except Exception as error:
            logger.warning("qrcode generation failed: %s", error)
            await helpers.send(interaction, "couldn't build a QR for that")
            return
        await helpers.send(interaction, file=discord.File(buffer, filename="qr.png"))

    @tree.command(name="passgen", description="Generate a strong random password.")
    @app_commands.describe(length="password length (4-128, default 16)")
    async def passgen(interaction: Interaction, length: int = 16) -> None:
        password = _random_password(length)
        await helpers.send(interaction, f"`{password}`", ephemeral=True)

    @tree.command(name="hash", description="Hash text with md5, sha1, sha256, or sha512.")
    @app_commands.describe(text="text to hash", algorithm="md5, sha1, sha256 or sha512")
    async def hash_cmd(interaction: Interaction, text: str, algorithm: str = "sha256") -> None:
        algo = algorithm.strip().lower()
        if algo not in _HASH_ALGOS:
            await helpers.deny(interaction, f"supported: {', '.join(sorted(_HASH_ALGOS))}")
            return
        digest = hashlib.new(algo, text.encode(), usedforsecurity=False).hexdigest()
        await helpers.send(interaction, helpers.clip(f"`{digest}`"))

    @tree.command(name="uuid", description="Generate a random UUID4.")
    async def uuid_cmd(interaction: Interaction) -> None:
        await helpers.send(interaction, f"`{uuid.uuid4()}`")

    @tree.command(name="calc", description="Safe arithmetic calculator (+ - * / % ** parens).")
    @app_commands.describe(expression="arithmetic expression to evaluate")
    async def calc(interaction: Interaction, expression: str) -> None:
        try:
            result = _safe_calc(expression)
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as error:
            await helpers.send(interaction, f"can't evaluate that: {error}")
            return
        await helpers.send(interaction, helpers.clip(f"{expression} = {result}"))

    @tree.command(name="randomcolor", description="Show a random hex colour swatch.")
    async def randomcolor(interaction: Interaction) -> None:
        value = secrets.randbits(24)
        hex_str = f"#{value:06X}"
        swatch = helpers.embed(
            title=hex_str,
            description=f"r={value >> 16 & 0xFF} g={value >> 8 & 0xFF} b={value & 0xFF}",
        )
        swatch.colour = discord.Colour(value)
        await helpers.send(interaction, embed=swatch)

    @tree.command(name="base", description="Convert an integer between bases 2-36.")
    @app_commands.describe(
        number="number to convert", from_base="source base (2-36)", to_base="target base (2-36)"
    )
    async def base_cmd(
        interaction: Interaction, number: str, from_base: int = 10, to_base: int = 2
    ) -> None:
        try:
            converted = _convert_base(number, from_base, to_base)
        except ValueError as error:
            await helpers.send(interaction, f"couldn't convert: {error}")
            return
        msg = f"{number} (base {from_base}) -> {converted} (base {to_base})"
        await helpers.send(interaction, msg)

    @tree.command(name="strlen", description="Count characters and words in text.")
    @app_commands.describe(text="text to measure")
    async def strlen(interaction: Interaction, text: str) -> None:
        body = text[:_TEXT_LIMIT]
        chars = len(body)
        words = len(body.split())
        await helpers.send(interaction, f"{chars} characters, {words} words")

    @tree.command(name="tinyurl", description="Shorten a URL via is.gd.")
    @app_commands.describe(url="URL to shorten")
    async def tinyurl(interaction: Interaction, url: str) -> None:
        await interaction.response.defer()
        encoded = urllib.parse.quote(url, safe="")
        try:
            short = await helpers.fetch_text(
                f"https://is.gd/create.php?format=simple&url={encoded}"
            )
        except Exception as error:
            logger.warning("tinyurl fetch failed: %s", error)
            await interaction.followup.send("couldn't reach the shortener")
            return
        await interaction.followup.send(helpers.clip(short.strip() or "no response"))

    @tree.command(name="iplookup", description="Look up basic info about an IP address.")
    @app_commands.describe(ip="IPv4 or IPv6 address")
    async def iplookup(interaction: Interaction, ip: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"http://ip-api.com/json/{urllib.parse.quote(ip)}")
        except Exception as error:
            logger.warning("iplookup failed: %s", error)
            await interaction.followup.send("couldn't reach the lookup service")
            return
        emb = helpers.embed(title=f"IP {data.get('query', ip)}")
        emb.add_field(name="country", value=str(data.get("country", "?")), inline=True)
        emb.add_field(name="city", value=str(data.get("city", "?")), inline=True)
        emb.add_field(name="isp", value=str(data.get("isp", "?")), inline=False)
        await interaction.followup.send(embed=emb)

    @tree.command(name="usergen", description="Generate a random fake user profile.")
    async def usergen(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://randomuser.me/api/")
            person = data["results"][0]
            full = f"{person['name']['first']} {person['name']['last']}"
            email = str(person["email"])
            country = str(person["location"]["country"])
        except Exception as error:
            logger.warning("usergen failed: %s", error)
            await interaction.followup.send("couldn't fetch a profile")
            return
        emb = helpers.embed(title=full, description=f"{email}\n{country}")
        await interaction.followup.send(embed=emb)

    @tree.command(name="domain", description="Resolve a domain to an IP and show its country.")
    @app_commands.describe(domain="hostname like example.com")
    async def domain(interaction: Interaction, domain: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"http://ip-api.com/json/{urllib.parse.quote(domain)}")
        except Exception as error:
            logger.warning("domain lookup failed: %s", error)
            await interaction.followup.send("couldn't reach the lookup service")
            return
        emb = helpers.embed(title=domain)
        emb.add_field(name="ip", value=str(data.get("query", "?")), inline=True)
        emb.add_field(name="country", value=str(data.get("country", "?")), inline=True)
        await interaction.followup.send(embed=emb)
