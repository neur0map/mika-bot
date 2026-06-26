"""Color palette utilities: hex/rgb conversions, swatches, gradients, names."""

from __future__ import annotations

import colorsys
import io
import re
import secrets
from typing import Any

import discord
from discord import Interaction, app_commands
from PIL import Image, ImageDraw

from mika.bot.commands import helpers

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")
_SWATCH_SIZE = 128
_GRADIENT_W = 320
_GRADIENT_H = 64
_BAD_HEX = "give me a #RRGGBB hex code"

_CSS_COLORS: dict[str, str] = {
    "black": "000000",
    "white": "ffffff",
    "red": "ff0000",
    "green": "008000",
    "blue": "0000ff",
    "yellow": "ffff00",
    "cyan": "00ffff",
    "magenta": "ff00ff",
    "silver": "c0c0c0",
    "gray": "808080",
    "grey": "808080",
    "maroon": "800000",
    "olive": "808000",
    "purple": "800080",
    "teal": "008080",
    "navy": "000080",
    "orange": "ffa500",
    "pink": "ffc0cb",
    "brown": "a52a2a",
    "gold": "ffd700",
    "indigo": "4b0082",
    "violet": "ee82ee",
    "lime": "00ff00",
    "coral": "ff7f50",
    "salmon": "fa8072",
    "khaki": "f0e68c",
    "tan": "d2b48c",
    "beige": "f5f5dc",
    "ivory": "fffff0",
    "lavender": "e6e6fa",
    "turquoise": "40e0d0",
}


def _parse_hex(value: str) -> tuple[int, int, int] | None:
    """Parse '#RRGGBB' or 'RRGGBB' into an (r, g, b) triple."""
    match = _HEX_RE.match(value.strip())
    if match is None:
        return None
    raw = match.group(1)
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _clamp(value: int) -> int:
    return max(0, min(255, value))


def _to_hex(r: int, g: int, b: int) -> str:
    return f"#{_clamp(r):02x}{_clamp(g):02x}{_clamp(b):02x}"


def _to_int(r: int, g: int, b: int) -> int:
    return (_clamp(r) << 16) | (_clamp(g) << 8) | _clamp(b)


def _rgb_to_hsl(r: int, g: int, b: int) -> tuple[int, int, int]:
    hue, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return round(hue * 360), round(sat * 100), round(light * 100)


def _shift_lightness(r: int, g: int, b: int, delta: float) -> tuple[int, int, int]:
    hue, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    light = max(0.0, min(1.0, light + delta))
    nr, ng, nb = colorsys.hls_to_rgb(hue, light, sat)
    return round(nr * 255), round(ng * 255), round(nb * 255)


def _swatch_png(r: int, g: int, b: int, size: int = _SWATCH_SIZE) -> io.BytesIO:
    img = Image.new("RGB", (size, size), (r, g, b))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _gradient_png(start: tuple[int, int, int], end: tuple[int, int, int]) -> io.BytesIO:
    img = Image.new("RGB", (_GRADIENT_W, _GRADIENT_H))
    draw = ImageDraw.Draw(img)
    span = max(1, _GRADIENT_W - 1)
    sr, sg, sb = start
    er, eg, eb = end
    for x in range(_GRADIENT_W):
        t = x / span
        color = (
            round(sr + (er - sr) * t),
            round(sg + (eg - sg) * t),
            round(sb + (eb - sb) * t),
        )
        draw.line([(x, 0), (x, _GRADIENT_H)], fill=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the color and palette commands."""

    @tree.command(name="hex2rgb", description="Convert a #RRGGBB hex code to RGB.")
    @app_commands.describe(hex_code="hex code like #ff8800")
    async def hex2rgb(interaction: Interaction, hex_code: str) -> None:
        rgb = _parse_hex(hex_code)
        if rgb is None:
            await helpers.deny(interaction, _BAD_HEX)
            return
        r, g, b = rgb
        emb = discord.Embed(
            title=_to_hex(r, g, b),
            description=f"R={r} G={g} B={b}",
            color=discord.Color(_to_int(r, g, b)),
        )
        await helpers.send(interaction, embed=emb)

    @tree.command(name="rgb2hex", description="Convert RGB values to a #RRGGBB hex code.")
    @app_commands.describe(r="red 0..255", g="green 0..255", b="blue 0..255")
    async def rgb2hex(interaction: Interaction, r: int, g: int, b: int) -> None:
        cr, cg, cb = _clamp(r), _clamp(g), _clamp(b)
        emb = discord.Embed(
            title=_to_hex(cr, cg, cb),
            description=f"R={cr} G={cg} B={cb}",
            color=discord.Color(_to_int(cr, cg, cb)),
        )
        await helpers.send(interaction, embed=emb)

    @tree.command(name="colorinfo", description="Show RGB and HSL for a hex color.")
    @app_commands.describe(hex_code="hex code like #ff8800")
    async def colorinfo(interaction: Interaction, hex_code: str) -> None:
        rgb = _parse_hex(hex_code)
        if rgb is None:
            await helpers.deny(interaction, _BAD_HEX)
            return
        r, g, b = rgb
        hue, sat, light = _rgb_to_hsl(r, g, b)
        emb = discord.Embed(
            title=_to_hex(r, g, b),
            description=f"RGB({r}, {g}, {b})\nHSL({hue}\u00b0, {sat}%, {light}%)",
            color=discord.Color(_to_int(r, g, b)),
        )
        await helpers.send(interaction, embed=emb)

    @tree.command(name="complementary", description="Show the complementary color.")
    @app_commands.describe(hex_code="hex code like #ff8800")
    async def complementary(interaction: Interaction, hex_code: str) -> None:
        rgb = _parse_hex(hex_code)
        if rgb is None:
            await helpers.deny(interaction, _BAD_HEX)
            return
        r, g, b = rgb
        cr, cg, cb = 255 - r, 255 - g, 255 - b
        emb = discord.Embed(
            title=f"{_to_hex(r, g, b)} \u2194 {_to_hex(cr, cg, cb)}",
            description=(
                f"input RGB({r}, {g}, {b})\ncomplement {_to_hex(cr, cg, cb)} RGB({cr}, {cg}, {cb})"
            ),
            color=discord.Color(_to_int(cr, cg, cb)),
        )
        await helpers.send(interaction, embed=emb)

    @tree.command(name="shades", description="Show lighter and darker shades of a color.")
    @app_commands.describe(hex_code="hex code like #ff8800")
    async def shades(interaction: Interaction, hex_code: str) -> None:
        rgb = _parse_hex(hex_code)
        if rgb is None:
            await helpers.deny(interaction, _BAD_HEX)
            return
        r, g, b = rgb
        steps = (-0.3, -0.15, 0.0, 0.15, 0.3)
        lines: list[str] = []
        for delta in steps:
            sr, sg, sb = _shift_lightness(r, g, b, delta)
            label = "base" if delta == 0 else f"{round(delta * 100):+d}%"
            lines.append(f"`{_to_hex(sr, sg, sb)}` {label}")
        emb = discord.Embed(
            title=f"shades of {_to_hex(r, g, b)}",
            description="\n".join(lines),
            color=discord.Color(_to_int(r, g, b)),
        )
        await helpers.send(interaction, embed=emb)

    @tree.command(name="palette", description="Generate a random 5-color palette.")
    async def palette(interaction: Interaction) -> None:
        colors = [
            (secrets.randbelow(256), secrets.randbelow(256), secrets.randbelow(256))
            for _ in range(5)
        ]
        lines = [f"`{_to_hex(r, g, b)}` RGB({r}, {g}, {b})" for r, g, b in colors]
        first = colors[0]
        emb = discord.Embed(
            title="random palette",
            description="\n".join(lines),
            color=discord.Color(_to_int(*first)),
        )
        await helpers.send(interaction, embed=emb)

    @tree.command(name="swatch", description="Render a solid-color PNG swatch.")
    @app_commands.describe(hex_code="hex code like #ff8800")
    async def swatch(interaction: Interaction, hex_code: str) -> None:
        rgb = _parse_hex(hex_code)
        if rgb is None:
            await helpers.deny(interaction, _BAD_HEX)
            return
        buf = _swatch_png(*rgb)
        filename = f"{_to_hex(*rgb)[1:]}.png"
        await helpers.send(interaction, file=discord.File(buf, filename=filename))

    @tree.command(name="gradient", description="Render a horizontal gradient between two colors.")
    @app_commands.describe(start="start hex code", end="end hex code")
    async def gradient(interaction: Interaction, start: str, end: str) -> None:
        s = _parse_hex(start)
        e = _parse_hex(end)
        if s is None or e is None:
            await helpers.deny(interaction, "give me two #RRGGBB hex codes")
            return
        buf = _gradient_png(s, e)
        await helpers.send(interaction, file=discord.File(buf, filename="gradient.png"))

    @tree.command(name="name2hex", description="Look up a common CSS color name.")
    @app_commands.describe(name="color name like red or coral")
    async def name2hex(interaction: Interaction, name: str) -> None:
        key = name.strip().lower()
        raw = _CSS_COLORS.get(key)
        if raw is None:
            await helpers.deny(interaction, "don't know that color name")
            return
        r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
        emb = discord.Embed(
            title=f"{key} = #{raw}",
            description=f"RGB({r}, {g}, {b})",
            color=discord.Color(int(raw, 16)),
        )
        await helpers.send(interaction, embed=emb)
