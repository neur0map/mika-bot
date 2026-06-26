"""Date, time, and timezone helpers: world clock, conversions, age, countdowns."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_WORLD_CITIES: tuple[tuple[str, str], ...] = (
    ("UTC", "UTC"),
    ("Los Angeles", "America/Los_Angeles"),
    ("New York", "America/New_York"),
    ("London", "Europe/London"),
    ("Paris", "Europe/Paris"),
    ("Tokyo", "Asia/Tokyo"),
    ("Sydney", "Australia/Sydney"),
)

_STAMP_STYLES: tuple[str, ...] = ("t", "T", "d", "D", "f", "F", "R")

_BAD_DATE = "date must look like YYYY-MM-DD"
_BAD_WHEN = "date must be YYYY-MM-DD or YYYY-MM-DD HH:MM[:SS]"
_BAD_ZONE = "unknown timezone, try IANA names like Europe/London"


def _parse_date(text: str) -> date:
    """Parse a strict YYYY-MM-DD date string."""
    return date.fromisoformat(text.strip())


def _parse_when(text: str) -> datetime:
    """Parse a date or date-time string, defaulting naive values to UTC."""
    parsed = datetime.fromisoformat(text.strip())
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _years_between(start: date, today: date) -> int:
    """Whole years from start up to today."""
    years = today.year - start.year
    if (today.month, today.day) < (start.month, start.day):
        years -= 1
    return years


def _stamp_lines(epoch: int) -> str:
    return "\n".join(f"`{style}` <t:{epoch}:{style}>" for style in _STAMP_STYLES)


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the date and time commands."""

    @tree.command(name="timein", description="Show the current time in an IANA timezone.")
    @app_commands.describe(zone="IANA timezone like Europe/London")
    async def timein(interaction: Interaction, zone: str) -> None:
        label = zone.strip()
        try:
            tz = ZoneInfo(label)
        except (ZoneInfoNotFoundError, ValueError):
            await helpers.deny(interaction, _BAD_ZONE)
            return
        now = datetime.now(tz)
        await helpers.send(interaction, f"{label}: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    @tree.command(name="worldclock", description="Show the current time in major world cities.")
    async def worldclock(interaction: Interaction) -> None:
        lines = []
        for label, name in _WORLD_CITIES:
            current = datetime.now(ZoneInfo(name))
            lines.append(f"**{label}** — {current.strftime('%Y-%m-%d %H:%M')}")
        await helpers.send(interaction, embed=helpers.embed("World clock", "\n".join(lines)))

    @tree.command(name="unixnow", description="Show the current Unix epoch and timestamp tag.")
    async def unixnow(interaction: Interaction) -> None:
        epoch = int(datetime.now(tz=UTC).timestamp())
        await helpers.send(interaction, f"epoch: `{epoch}`\n<t:{epoch}:F>")

    @tree.command(name="fromunix", description="Render Discord timestamp tags for a Unix epoch.")
    @app_commands.describe(epoch="Unix epoch seconds")
    async def fromunix(interaction: Interaction, epoch: int) -> None:
        try:
            datetime.fromtimestamp(epoch, tz=UTC)
        except (OverflowError, OSError, ValueError):
            await helpers.deny(interaction, "epoch out of range")
            return
        await helpers.send(interaction, _stamp_lines(epoch))

    @tree.command(name="age", description="Compute age in years from a birthdate (YYYY-MM-DD).")
    @app_commands.describe(birthdate="birthdate in YYYY-MM-DD")
    async def age(interaction: Interaction, birthdate: str) -> None:
        try:
            born = _parse_date(birthdate)
        except ValueError:
            await helpers.deny(interaction, _BAD_DATE)
            return
        today = datetime.now(tz=UTC).date()
        if born > today:
            await helpers.deny(interaction, "birthdate is in the future")
            return
        years = _years_between(born, today)
        await helpers.send(interaction, f"age: {years} years")

    @tree.command(name="daysbetween", description="Count days between two YYYY-MM-DD dates.")
    @app_commands.describe(start="start date YYYY-MM-DD", end="end date YYYY-MM-DD")
    async def daysbetween(interaction: Interaction, start: str, end: str) -> None:
        try:
            start_d = _parse_date(start)
            end_d = _parse_date(end)
        except ValueError:
            await helpers.deny(interaction, _BAD_DATE)
            return
        delta = (end_d - start_d).days
        await helpers.send(interaction, f"{delta} days")

    @tree.command(name="weekday", description="Show the weekday for a YYYY-MM-DD date.")
    @app_commands.describe(date="date in YYYY-MM-DD")
    async def weekday(interaction: Interaction, date: str) -> None:
        try:
            value = _parse_date(date)
        except ValueError:
            await helpers.deny(interaction, _BAD_DATE)
            return
        await helpers.send(interaction, f"{value.isoformat()} is a {value.strftime('%A')}")

    @tree.command(name="countdown", description="Discord relative timestamp counting to a date.")
    @app_commands.describe(date="target date YYYY-MM-DD")
    async def countdown(interaction: Interaction, date: str) -> None:
        try:
            target = _parse_date(date)
        except ValueError:
            await helpers.deny(interaction, _BAD_DATE)
            return
        moment = datetime(target.year, target.month, target.day, tzinfo=UTC)
        epoch = int(moment.timestamp())
        await helpers.send(interaction, f"<t:{epoch}:R>")

    @tree.command(name="timestamp", description="Discord timestamp tags in every style.")
    @app_commands.describe(date="YYYY-MM-DD or YYYY-MM-DD HH:MM[:SS]")
    async def timestamp(interaction: Interaction, date: str) -> None:
        try:
            when = _parse_when(date)
        except ValueError:
            await helpers.deny(interaction, _BAD_WHEN)
            return
        epoch = int(when.timestamp())
        await helpers.send(interaction, _stamp_lines(epoch))
