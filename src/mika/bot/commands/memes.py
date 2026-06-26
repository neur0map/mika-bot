"""Avatar effect commands and a couple of API-backed picks."""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import Any

import discord
from discord import Interaction, app_commands
from PIL import Image, ImageDraw, ImageEnhance, ImageFile, ImageFilter, ImageFont, ImageOps

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

ImageFile.LOAD_TRUNCATED_IMAGES = True

EffectFn = Callable[[Image.Image], Image.Image]


def _grayscale(im: Image.Image) -> Image.Image:
    return ImageOps.grayscale(im).convert("RGBA")


def _invert(im: Image.Image) -> Image.Image:
    return ImageOps.invert(im.convert("RGB")).convert("RGBA")


def _blur(im: Image.Image) -> Image.Image:
    return im.filter(ImageFilter.GaussianBlur(8))


def _pixelate(im: Image.Image) -> Image.Image:
    w, h = im.size
    small = im.resize((max(8, w // 12), max(8, h // 12)), Image.Resampling.NEAREST)
    return small.resize((w, h), Image.Resampling.NEAREST)


def _sepia(im: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(im)
    return ImageOps.colorize(gray, black=(20, 10, 0), white=(255, 224, 180)).convert("RGBA")


def _mirror(im: Image.Image) -> Image.Image:
    return ImageOps.mirror(im)


def _flip(im: Image.Image) -> Image.Image:
    return ImageOps.flip(im)


def _rotate(im: Image.Image) -> Image.Image:
    return im.rotate(180, expand=False)


def _brighten(im: Image.Image) -> Image.Image:
    return ImageEnhance.Brightness(im).enhance(1.6)


def _darken(im: Image.Image) -> Image.Image:
    return ImageEnhance.Brightness(im).enhance(0.5)


def _contrast(im: Image.Image) -> Image.Image:
    return ImageEnhance.Contrast(im).enhance(1.8)


def _edge(im: Image.Image) -> Image.Image:
    return im.convert("RGB").filter(ImageFilter.FIND_EDGES).convert("RGBA")


def _posterize(im: Image.Image) -> Image.Image:
    return ImageOps.posterize(im.convert("RGB"), 3).convert("RGBA")


def _solarize(im: Image.Image) -> Image.Image:
    return ImageOps.solarize(im.convert("RGB"), threshold=128).convert("RGBA")


def _deepfry(im: Image.Image) -> Image.Image:
    rgb = im.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(4.0)
    rgb = ImageEnhance.Color(rgb).enhance(4.0)
    rgb = ImageEnhance.Sharpness(rgb).enhance(3.0)
    return rgb.filter(ImageFilter.SHARPEN).convert("RGBA")


def _wasted(im: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(im).convert("RGBA")
    tint = Image.new("RGBA", gray.size, (255, 0, 0, 90))
    base = Image.alpha_composite(gray, tint)
    draw = ImageDraw.Draw(base)
    font = ImageFont.load_default()
    text = "WASTED"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pos = ((base.width - tw) // 2, (base.height - th) // 2)
    draw.text(pos, text, fill=(220, 0, 0, 255), font=font)
    return base


def _jail(im: Image.Image) -> Image.Image:
    base = im.convert("RGBA")
    dim = Image.new("RGBA", base.size, (0, 0, 0, 80))
    base = Image.alpha_composite(base, dim)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = base.size
    bars = 6
    bar_w = max(2, w // 40)
    spacing = max(1, w // bars)
    for i in range(bars + 1):
        x = i * spacing
        draw.rectangle((x, 0, x + bar_w, h), fill=(20, 20, 20, 200))
    return Image.alpha_composite(base, overlay)


def _pride(im: Image.Image) -> Image.Image:
    base = im.convert("RGBA")
    w, h = base.size
    colors = [
        (228, 3, 3),
        (255, 140, 0),
        (255, 237, 0),
        (0, 128, 38),
        (0, 77, 255),
        (117, 7, 135),
    ]
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    stripe_h = max(1, h // len(colors))
    for i, color in enumerate(colors):
        y0 = i * stripe_h
        if y0 >= h:
            break
        y1 = h if i == len(colors) - 1 else min(h, y0 + stripe_h)
        draw.rectangle((0, y0, w, y1), fill=(*color, 110))
    return Image.alpha_composite(base, overlay)


def _tint(im: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    gray = ImageOps.grayscale(im)
    return ImageOps.colorize(gray, black=(0, 0, 0), white=color).convert("RGBA")


def _blurple(im: Image.Image) -> Image.Image:
    return _tint(im, (88, 101, 242))


def _redtint(im: Image.Image) -> Image.Image:
    return _tint(im, (220, 38, 38))


_EFFECTS: list[tuple[str, str, EffectFn]] = [
    ("grayscale", "Drain the color from an avatar.", _grayscale),
    ("invert", "Invert the colors of an avatar.", _invert),
    ("blur", "Gaussian blur on an avatar.", _blur),
    ("pixelate", "Crunch an avatar down to chunky pixels.", _pixelate),
    ("sepia", "Warm sepia wash on an avatar.", _sepia),
    ("mirror", "Flip an avatar horizontally.", _mirror),
    ("flip", "Flip an avatar vertically.", _flip),
    ("rotate", "Spin an avatar 180 degrees.", _rotate),
    ("brighten", "Lighten an avatar.", _brighten),
    ("darken", "Darken an avatar.", _darken),
    ("contrast", "Crank the contrast on an avatar.", _contrast),
    ("edge", "Find edges in an avatar.", _edge),
    ("posterize", "Posterize an avatar.", _posterize),
    ("solarize", "Solarize an avatar.", _solarize),
    ("deepfry", "Deep-fry an avatar.", _deepfry),
    ("wasted", "GTA-style 'WASTED' on an avatar.", _wasted),
    ("jail", "Throw an avatar behind bars.", _jail),
    ("pride", "Rainbow flag over an avatar.", _pride),
    ("blurple", "Blurple monochrome tint.", _blurple),
    ("redtint", "Red monochrome tint.", _redtint),
]


def _render(image: Image.Image, fn: EffectFn) -> io.BytesIO:
    out = fn(image)
    if out.mode != "RGBA":
        out = out.convert("RGBA")
    buffer = io.BytesIO()
    out.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _register_effect(
    tree: app_commands.CommandTree[Any], name: str, description: str, fn: EffectFn
) -> None:
    @tree.command(name=name, description=description)
    async def effect(interaction: Interaction, user: discord.Member | None = None) -> None:
        await interaction.response.defer()
        target = user or interaction.user
        try:
            avatar_bytes = await helpers.fetch_bytes(str(target.display_avatar.url))
            with Image.open(io.BytesIO(avatar_bytes)) as source:
                image = source.convert("RGBA")
            buffer = _render(image, fn)
        except Exception as error:
            logger.warning("%s effect failed: %s", name, error)
            await interaction.followup.send("couldn't render that one")
            return
        await interaction.followup.send(file=discord.File(buffer, filename=f"{name}.png"))


def _heart_bar(percent: int, slots: int = 10) -> str:
    filled = round(percent / 100 * slots)
    return "\u2764\ufe0f" * filled + "\U0001f90d" * (slots - filled)


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register meme and avatar-effect commands."""
    for name, description, fn in _EFFECTS:
        _register_effect(tree, name, description, fn)

    @tree.command(name="meme", description="A random meme.")
    async def meme(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://meme-api.com/gimme")
            url = str(data["url"])
        except Exception as error:
            logger.warning("meme fetch failed: %s", error)
            await interaction.followup.send("couldn't fetch a meme right now")
            return
        await interaction.followup.send(url)

    @tree.command(name="ship", description="Compute a love percentage between two users.")
    async def ship(
        interaction: Interaction,
        user1: discord.Member,
        user2: discord.Member | None = None,
    ) -> None:
        other = user2 or interaction.user
        a, b = sorted((int(user1.id), int(other.id)))
        percent = (a * 31 + b * 17) % 101
        bar = _heart_bar(percent)
        title = f"{user1.display_name} \u2764 {other.display_name}"
        description = f"**{percent}%** match\n{bar}"
        await helpers.send(interaction, embed=helpers.embed(title, description))
