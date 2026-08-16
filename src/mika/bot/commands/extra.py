"""Translate, Minecraft, polls, embeds and HTTP utility commands."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from discord import Embed, Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_REGIONAL_A = 0x1F1E6
_MAX_OPTIONS = 10
_MIN_HTTP = 100
_MAX_HTTP = 599
_MIN_PX = 16
_MAX_PX = 2000

_HTTP_STATUS: dict[int, str] = {
    100: "Continue",
    101: "Switching Protocols",
    200: "OK",
    201: "Created",
    202: "Accepted",
    204: "No Content",
    206: "Partial Content",
    301: "Moved Permanently",
    302: "Found",
    304: "Not Modified",
    307: "Temporary Redirect",
    308: "Permanent Redirect",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    408: "Request Timeout",
    409: "Conflict",
    410: "Gone",
    418: "I'm a teapot",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    451: "Unavailable For Legal Reasons",
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}


def _letter(idx: int) -> str:
    """Return the regional-indicator letter for index 0..9."""
    return chr(_REGIONAL_A + idx)


def _split_options(raw: str) -> list[str]:
    """Parse a comma-separated option string into a clean list."""
    return [part.strip() for part in raw.split(",") if part.strip()]


def _poll_options(raw: str) -> list[str]:
    """Return at least two options, defaulting to yes/no."""
    parts = _split_options(raw)
    if len(parts) < 2:
        return ["yes", "no"]
    return parts[:_MAX_OPTIONS]


def _poll_embed(question: str, options: list[str]) -> Embed:
    """Build a poll embed listing options with regional-indicator letters."""
    body = "\n".join(f"{_letter(i)} {opt}" for i, opt in enumerate(options))
    return helpers.embed(question, body)


async def _react_letters(interaction: Interaction, count: int) -> None:
    """Best-effort add A..N reactions to the response message."""
    try:
        msg = await interaction.original_response()
        for i in range(count):
            await msg.add_reaction(_letter(i))
    except Exception as error:
        logger.warning("poll reactions failed: %s", error)


async def _react_thumbs(interaction: Interaction) -> None:
    """Best-effort add thumbs up/down reactions to the response message."""
    try:
        msg = await interaction.original_response()
        await msg.add_reaction("\U0001f44d")
        await msg.add_reaction("\U0001f44e")
    except Exception as error:
        logger.warning("thumbs reactions failed: %s", error)


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register translate, Minecraft, poll and HTTP-utility commands."""

    @tree.command(name="translate", description="Translate text via Lingva.")
    @app_commands.describe(
        text="text to translate",
        to_lang="target language code (e.g. es, fr, ja)",
        from_lang="source language code or 'auto'",
    )
    async def translate(
        interaction: Interaction, text: str, to_lang: str, from_lang: str = "auto"
    ) -> None:
        """Translate text from one language to another."""
        await interaction.response.defer()
        try:
            url = f"https://lingva.ml/api/v1/{from_lang}/{to_lang}/{quote(text)}"
            data = await helpers.fetch_json(url)
            out = str(data.get("translation") or "").strip()
            await interaction.followup.send(helpers.clip(out) or "no translation")
        except Exception as error:
            logger.warning("translate failed: %s", error)
            await interaction.followup.send("couldn't translate that")

    @tree.command(name="detectlang", description="Best-effort language detection.")
    @app_commands.describe(text="text to inspect")
    async def detectlang(interaction: Interaction, text: str) -> None:
        """Detect the source language of a phrase via Lingva."""
        await interaction.response.defer()
        try:
            url = f"https://lingva.ml/api/v1/auto/en/{quote(text)}"
            data = await helpers.fetch_json(url)
            info = data.get("info")
            detected = info.get("detectedSource") if isinstance(info, dict) else None
            label = str(detected) if detected else "unknown"
            await interaction.followup.send(f"detected language: `{label}`")
        except Exception as error:
            logger.warning("detectlang failed: %s", error)
            await interaction.followup.send("couldn't detect that language")

    @tree.command(name="mcserver", description="Look up a Minecraft server.")
    @app_commands.describe(address="server address (host or host:port)")
    async def mcserver(interaction: Interaction, address: str) -> None:
        """Show status, players and MOTD for a Minecraft server."""
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"https://api.mcsrvstat.us/3/{address}")
            online = bool(data.get("online"))
            raw_players = data.get("players")
            players = raw_players if isinstance(raw_players, dict) else {}
            raw_motd = data.get("motd")
            motd = raw_motd if isinstance(raw_motd, dict) else {}
            clean = motd.get("clean")
            tagline = str(clean[0]) if isinstance(clean, list) and clean else ""
            emb = helpers.embed(address, "online" if online else "offline")
            count = f"{players.get('online', 0)}/{players.get('max', 0)}"
            emb.add_field(name="Players", value=count)
            emb.add_field(name="Version", value=str(data.get("version") or "n/a"))
            if tagline:
                emb.add_field(name="MOTD", value=helpers.clip(tagline, 200), inline=False)
            await interaction.followup.send(embed=emb)
        except Exception as error:
            logger.warning("mcserver failed: %s", error)
            await interaction.followup.send("couldn't reach that server")

    @tree.command(name="mcuuid", description="Resolve a Minecraft account UUID.")
    @app_commands.describe(username="Minecraft username")
    async def mcuuid(interaction: Interaction, username: str) -> None:
        """Look up the Mojang UUID for a Minecraft username."""
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(
                f"https://api.mojang.com/users/profiles/minecraft/{username}"
            )
            name = str(data.get("name") or username)
            uid = str(data.get("id") or "")
            if not uid:
                raise ValueError("missing uuid")
            await interaction.followup.send(f"**{name}** `{uid}`")
        except Exception as error:
            logger.warning("mcuuid failed: %s", error)
            await interaction.followup.send("couldn't find that account")

    @tree.command(name="mcskin", description="Render a Minecraft player's skin.")
    @app_commands.describe(username="Minecraft username")
    async def mcskin(interaction: Interaction, username: str) -> None:
        """Show the 3D body render of a Minecraft player skin."""
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(
                f"https://api.mojang.com/users/profiles/minecraft/{username}"
            )
            uid = str(data.get("id") or "")
            if not uid:
                raise ValueError("missing uuid")
            name = str(data.get("name") or username)
            emb = helpers.embed(name)
            emb.set_image(url=f"https://crafatar.com/renders/body/{uid}")
            await interaction.followup.send(embed=emb)
        except Exception as error:
            logger.warning("mcskin failed: %s", error)
            await interaction.followup.send("couldn't find that skin")

    @tree.command(name="httpcat", description="Show an HTTP cat for a status code.")
    @app_commands.describe(code="HTTP status code")
    async def httpcat(interaction: Interaction, code: int) -> None:
        """Embed an http.cat image for the given status code."""
        clamped = max(_MIN_HTTP, min(_MAX_HTTP, code))
        emb = helpers.embed(f"HTTP {clamped}")
        emb.set_image(url=f"https://http.cat/{clamped}.jpg")
        await helpers.send(interaction, embed=emb)

    @tree.command(name="httpstatus", description="Describe an HTTP status code.")
    @app_commands.describe(code="HTTP status code")
    async def httpstatus(interaction: Interaction, code: int) -> None:
        """Look up the standard label for an HTTP status code."""
        label = _HTTP_STATUS.get(code, "Unknown Status")
        await helpers.send(interaction, f"**{code}** {label}")

    @tree.command(name="placeholder", description="Send a placeholder image of any size.")
    @app_commands.describe(width="image width in px", height="image height in px")
    async def placeholder(interaction: Interaction, width: int, height: int) -> None:
        """Embed a placeholder image clamped to a sane size."""
        w = max(_MIN_PX, min(_MAX_PX, width))
        h = max(_MIN_PX, min(_MAX_PX, height))
        emb = helpers.embed(f"{w}x{h}")
        emb.set_image(url=f"https://placehold.co/{w}x{h}.png")
        await helpers.send(interaction, embed=emb)

    @tree.command(name="poll", description="Start a multi-option poll.")
    @app_commands.describe(
        question="poll question",
        options="comma-separated options (2-10); omit for yes/no",
    )
    async def poll(interaction: Interaction, question: str, options: str = "") -> None:
        """Post a poll embed and best-effort add letter reactions."""
        opts = _poll_options(options)
        await helpers.send(interaction, embed=_poll_embed(question, opts))
        await _react_letters(interaction, len(opts))

    @tree.command(name="quickpoll", description="Start a yes/no poll.")
    @app_commands.describe(question="poll question")
    async def quickpoll(interaction: Interaction, question: str) -> None:
        """Post a yes/no poll and best-effort add thumbs reactions."""
        emb = helpers.embed(question, "\U0001f44d yes\n\U0001f44e no")
        await helpers.send(interaction, embed=emb)
        await _react_thumbs(interaction)

    @tree.command(name="embed", description="Send a custom embed.")
    @app_commands.describe(title="embed title", description="embed description")
    async def embed_cmd(interaction: Interaction, title: str, description: str) -> None:
        """Build a plain embed from a title and description."""
        await helpers.send(interaction, embed=helpers.embed(title, description))
