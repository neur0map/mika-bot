"""Unit and format conversions: temperature, length, weight, currency and more."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_TEMP_UNITS = ("c", "f", "k")
_LENGTH_TO_M: dict[str, float] = {
    "m": 1.0,
    "km": 1000.0,
    "mi": 1609.344,
    "ft": 0.3048,
    "in": 0.0254,
    "cm": 0.01,
    "yd": 0.9144,
}
_WEIGHT_TO_G: dict[str, float] = {
    "g": 1.0,
    "kg": 1000.0,
    "lb": 453.59237,
    "oz": 28.349523125,
    "st": 6350.29318,
}
_SPEED_TO_MS: dict[str, float] = {
    "ms": 1.0,
    "kmh": 1.0 / 3.6,
    "mph": 0.44704,
    "knot": 0.514444,
}
_BYTE_TO_B: dict[str, float] = {
    "b": 1.0,
    "kb": 1024.0,
    "mb": 1024.0**2,
    "gb": 1024.0**3,
    "tb": 1024.0**4,
}
_BYTE_ORDER = ("b", "kb", "mb", "gb", "tb")

_ROMAN_PAIRS: list[tuple[int, str]] = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

_FRANKFURTER = "https://api.frankfurter.app/latest"

_HELP_TEMP = "use one of c, f, k"
_HELP_LENGTH = "use one of m, km, mi, ft, in, cm, yd"
_HELP_WEIGHT = "use one of g, kg, lb, oz, st"
_HELP_SPEED = "use one of kmh, mph, ms, knot"
_HELP_BYTE = "use one of b, kb, mb, gb, tb"


def _to_celsius(value: float, unit: str) -> float:
    if unit == "c":
        return value
    if unit == "f":
        return (value - 32.0) * 5.0 / 9.0
    return value - 273.15


def _from_celsius(value: float, unit: str) -> float:
    if unit == "c":
        return value
    if unit == "f":
        return value * 9.0 / 5.0 + 32.0
    return value + 273.15


def _convert_via(value: float, src: str, dst: str, table: dict[str, float]) -> float:
    return value * table[src] / table[dst]


def _to_roman(number: int) -> str:
    out: list[str] = []
    remaining = number
    for amount, symbol in _ROMAN_PAIRS:
        count, remaining = divmod(remaining, amount)
        out.append(symbol * count)
    return "".join(out)


def _from_roman(numeral: str) -> int:
    total = 0
    prev = 0
    for char in reversed(numeral):
        value = _ROMAN_VALUES[char]
        total += -value if value < prev else value
        prev = value
    return total


def _valid_roman(numeral: str) -> bool:
    upper = numeral.strip().upper()
    if not upper or any(c not in _ROMAN_VALUES for c in upper):
        return False
    value = _from_roman(upper)
    return 1 <= value <= 3999 and _to_roman(value) == upper


def _parse_hm(text: str) -> tuple[int, int]:
    hours_str, sep, minutes_str = text.strip().partition(":")
    if not sep:
        raise ValueError("missing colon")
    hours, minutes = int(hours_str), int(minutes_str)
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        raise ValueError("out of range")
    return hours, minutes


def _format_bytes(value: float, unit: str) -> str:
    total_bytes = value * _BYTE_TO_B[unit]
    lines = [f"{value} {unit} ="]
    for code in _BYTE_ORDER:
        lines.append(f"  {round(total_bytes / _BYTE_TO_B[code], 6)} {code}")
    return "\n".join(lines)


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the unit and format conversion commands."""

    @tree.command(name="temperature", description="Convert temperature between C, F, and K.")
    @app_commands.describe(value="numeric value", from_unit="c, f, k", to_unit="c, f, k")
    async def temperature(
        interaction: Interaction, value: float, from_unit: str, to_unit: str
    ) -> None:
        src = from_unit.strip().lower()
        dst = to_unit.strip().lower()
        if src not in _TEMP_UNITS or dst not in _TEMP_UNITS:
            await helpers.deny(interaction, _HELP_TEMP)
            return
        result = _from_celsius(_to_celsius(value, src), dst)
        await helpers.send(interaction, f"{value} {src.upper()} = {round(result, 4)} {dst.upper()}")

    @tree.command(name="length", description="Convert length across metric and imperial units.")
    @app_commands.describe(
        value="numeric value",
        from_unit="m/km/mi/ft/in/cm/yd",
        to_unit="m/km/mi/ft/in/cm/yd",
    )
    async def length(interaction: Interaction, value: float, from_unit: str, to_unit: str) -> None:
        src = from_unit.strip().lower()
        dst = to_unit.strip().lower()
        if src not in _LENGTH_TO_M or dst not in _LENGTH_TO_M:
            await helpers.deny(interaction, _HELP_LENGTH)
            return
        result = _convert_via(value, src, dst, _LENGTH_TO_M)
        await helpers.send(interaction, f"{value} {src} = {round(result, 6)} {dst}")

    @tree.command(name="weight", description="Convert weight across metric and imperial units.")
    @app_commands.describe(
        value="numeric value",
        from_unit="g/kg/lb/oz/st",
        to_unit="g/kg/lb/oz/st",
    )
    async def weight(interaction: Interaction, value: float, from_unit: str, to_unit: str) -> None:
        src = from_unit.strip().lower()
        dst = to_unit.strip().lower()
        if src not in _WEIGHT_TO_G or dst not in _WEIGHT_TO_G:
            await helpers.deny(interaction, _HELP_WEIGHT)
            return
        result = _convert_via(value, src, dst, _WEIGHT_TO_G)
        await helpers.send(interaction, f"{value} {src} = {round(result, 6)} {dst}")

    @tree.command(name="roman", description="Convert an integer (1-3999) to Roman numerals.")
    @app_commands.describe(number="integer between 1 and 3999")
    async def roman(interaction: Interaction, number: int) -> None:
        if not 1 <= number <= 3999:
            await helpers.deny(interaction, "number must be between 1 and 3999")
            return
        await helpers.send(interaction, f"{number} = {_to_roman(number)}")

    @tree.command(name="fromroman", description="Convert a Roman numeral back to an integer.")
    @app_commands.describe(numeral="Roman numeral string (1-3999)")
    async def fromroman(interaction: Interaction, numeral: str) -> None:
        if not _valid_roman(numeral):
            await helpers.deny(interaction, "not a valid Roman numeral")
            return
        upper = numeral.strip().upper()
        await helpers.send(interaction, f"{upper} = {_from_roman(upper)}")

    @tree.command(name="bytesize", description="Show a byte value across b/kb/mb/gb/tb scales.")
    @app_commands.describe(value="numeric value", unit="b, kb, mb, gb, tb")
    async def bytesize(interaction: Interaction, value: float, unit: str) -> None:
        src = unit.strip().lower()
        if src not in _BYTE_TO_B:
            await helpers.deny(interaction, _HELP_BYTE)
            return
        await helpers.send(interaction, helpers.clip(_format_bytes(value, src)))

    @tree.command(name="timezone", description="Convert HH:MM between IANA timezones.")
    @app_commands.describe(
        time="HH:MM",
        from_tz="source IANA zone like UTC or Europe/London",
        to_tz="target IANA zone like America/New_York",
    )
    async def timezone_cmd(interaction: Interaction, time: str, from_tz: str, to_tz: str) -> None:
        try:
            hours, minutes = _parse_hm(time)
        except ValueError:
            await helpers.deny(interaction, "time must look like HH:MM")
            return
        try:
            src_zone = ZoneInfo(from_tz)
            dst_zone = ZoneInfo(to_tz)
        except (ZoneInfoNotFoundError, ValueError):
            await helpers.deny(interaction, "unknown timezone, try IANA names like Europe/London")
            return
        moment = datetime.now(src_zone).replace(hour=hours, minute=minutes, second=0, microsecond=0)
        converted = moment.astimezone(dst_zone)
        await helpers.send(
            interaction,
            f"{time} {from_tz} = {converted.strftime('%H:%M')} {to_tz}",
        )

    @tree.command(name="speed", description="Convert speed between kmh, mph, ms, and knot.")
    @app_commands.describe(
        value="numeric value", from_unit="kmh/mph/ms/knot", to_unit="kmh/mph/ms/knot"
    )
    async def speed(interaction: Interaction, value: float, from_unit: str, to_unit: str) -> None:
        src = from_unit.strip().lower()
        dst = to_unit.strip().lower()
        if src not in _SPEED_TO_MS or dst not in _SPEED_TO_MS:
            await helpers.deny(interaction, _HELP_SPEED)
            return
        result = _convert_via(value, src, dst, _SPEED_TO_MS)
        await helpers.send(interaction, f"{value} {src} = {round(result, 4)} {dst}")

    @tree.command(name="currency", description="Convert currency using daily ECB rates.")
    @app_commands.describe(
        amount="amount to convert",
        from_cur="ISO 4217 code like USD",
        to_cur="ISO 4217 code like EUR",
    )
    async def currency(interaction: Interaction, amount: float, from_cur: str, to_cur: str) -> None:
        await interaction.response.defer()
        src = from_cur.strip().upper()
        dst = to_cur.strip().upper()
        params: dict[str, Any] = {"amount": amount, "from": src, "to": dst}
        try:
            data = await helpers.fetch_json(_FRANKFURTER, **params)
            converted = float(data["rates"][dst])
        except Exception as error:
            logger.warning("currency fetch failed: %s", error)
            await interaction.followup.send("couldn't reach the rates service")
            return
        await interaction.followup.send(f"{amount} {src} = {round(converted, 4)} {dst}")
