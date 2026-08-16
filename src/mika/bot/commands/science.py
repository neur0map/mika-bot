"""Math and science helpers: primes, factorials, statistics and basic algebra."""

from __future__ import annotations

import math
import statistics
from typing import Any

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_FACT_MAX = 1000
_FIB_MAX = 1000
_PRIME_INPUT_MAX = 10**9
_COLLATZ_MAX = 10**9
_NTH_PRIME_MAX = 10000
_ROUND_DIGITS_MAX = 15
_SMALL_PRIMES = (2, 3, 5, 7, 11)
_PARSE_HELP = "give me a list of numbers separated by commas or spaces"


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(value, hi))


def _is_prime(number: int) -> bool:
    if number < 2:
        return False
    if number < 4:
        return True
    if number % 2 == 0:
        return False
    limit = math.isqrt(number)
    return all(number % divisor != 0 for divisor in range(3, limit + 1, 2))


def _prime_factors(number: int) -> list[int]:
    factors: list[int] = []
    remaining = number
    divisor = 2
    while divisor * divisor <= remaining:
        while remaining % divisor == 0:
            factors.append(divisor)
            remaining //= divisor
        divisor += 1
    if remaining > 1:
        factors.append(remaining)
    return factors


def _nth_prime(index: int) -> int:
    if index <= len(_SMALL_PRIMES):
        return _SMALL_PRIMES[index - 1]
    log_n = math.log(index)
    limit = int(index * (log_n + math.log(log_n))) + 16
    sieve = bytearray(b"\x01") * (limit + 1)
    sieve[0] = 0
    sieve[1] = 0
    for i in range(2, math.isqrt(limit) + 1):
        if sieve[i]:
            step = i
            start = i * i
            sieve[start : limit + 1 : step] = b"\x00" * len(range(start, limit + 1, step))
    count = 0
    for candidate, flag in enumerate(sieve):
        if flag:
            count += 1
            if count == index:
                return candidate
    return 0


def _collatz_steps(number: int) -> int:
    steps = 0
    current = number
    while current != 1:
        current = current // 2 if current % 2 == 0 else 3 * current + 1
        steps += 1
    return steps


def _fibonacci(index: int) -> int:
    a, b = 0, 1
    for _ in range(index):
        a, b = b, a + b
    return a


def _parse_numbers(text: str) -> list[float]:
    cleaned = text.replace(",", " ")
    parts = [chunk for chunk in cleaned.split() if chunk]
    if not parts:
        raise ValueError("empty input")
    return [float(part) for part in parts]


def _format_factors(number: int, factors: list[int]) -> str:
    counts: dict[int, int] = {}
    for factor in factors:
        counts[factor] = counts.get(factor, 0) + 1
    parts = [f"{p}^{c}" if c > 1 else str(p) for p, c in sorted(counts.items())]
    return f"{number} = {' * '.join(parts)}"


def _quadratic_roots(a: float, b: float, c: float) -> tuple[float, ...]:
    if a == 0:
        if b == 0:
            raise ValueError("a and b are both 0, no unique solution")
        return (-c / b,)
    disc = b * b - 4 * a * c
    if disc < 0:
        raise ValueError("no real roots (discriminant is negative)")
    root = math.sqrt(disc)
    return ((-b + root) / (2 * a), (-b - root) / (2 * a))


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the math and science commands on the tree."""

    @tree.command(name="isprime", description="Check whether an integer is prime.")
    @app_commands.describe(number="non-negative integer to test")
    async def isprime(interaction: Interaction, number: int) -> None:
        if number < 0 or number > _PRIME_INPUT_MAX:
            await helpers.deny(interaction, f"give me an integer between 0 and {_PRIME_INPUT_MAX}")
            return
        verdict = "prime" if _is_prime(number) else "not prime"
        await helpers.send(interaction, f"{number} is {verdict}")

    @tree.command(name="factorial", description="Compute n! for 0 <= n <= 1000.")
    @app_commands.describe(number="non-negative integer (clamped to 0-1000)")
    async def factorial(interaction: Interaction, number: int) -> None:
        if number < 0:
            await helpers.deny(interaction, "factorial needs a non-negative integer")
            return
        clamped = _clamp(number, 0, _FACT_MAX)
        result = math.factorial(clamped)
        await helpers.send(interaction, helpers.clip(f"{clamped}! = {result}"))

    @tree.command(name="fibonacci", description="The nth Fibonacci number (0 <= n <= 1000).")
    @app_commands.describe(n="index in the sequence (clamped to 0-1000)")
    async def fibonacci(interaction: Interaction, n: int) -> None:
        if n < 0:
            await helpers.deny(interaction, "fibonacci needs a non-negative index")
            return
        clamped = _clamp(n, 0, _FIB_MAX)
        value = _fibonacci(clamped)
        await helpers.send(interaction, helpers.clip(f"fib({clamped}) = {value}"))

    @tree.command(name="gcd", description="Greatest common divisor of two integers.")
    @app_commands.describe(a="first integer", b="second integer")
    async def gcd(interaction: Interaction, a: int, b: int) -> None:
        await helpers.send(interaction, f"gcd({a}, {b}) = {math.gcd(a, b)}")

    @tree.command(name="lcm", description="Least common multiple of two integers.")
    @app_commands.describe(a="first integer", b="second integer")
    async def lcm(interaction: Interaction, a: int, b: int) -> None:
        await helpers.send(interaction, f"lcm({a}, {b}) = {math.lcm(a, b)}")

    @tree.command(name="primefactors", description="Prime factorisation of a positive integer.")
    @app_commands.describe(number="integer between 2 and 1,000,000,000")
    async def primefactors(interaction: Interaction, number: int) -> None:
        if number < 2 or number > _PRIME_INPUT_MAX:
            await helpers.deny(interaction, f"give me an integer between 2 and {_PRIME_INPUT_MAX}")
            return
        factors = _prime_factors(number)
        await helpers.send(interaction, helpers.clip(_format_factors(number, factors)))

    @tree.command(name="stats", description="Mean, median, min, max and stdev of a list.")
    @app_commands.describe(numbers="comma- or space-separated numbers")
    async def stats(interaction: Interaction, numbers: str) -> None:
        try:
            values = _parse_numbers(numbers)
        except ValueError:
            await helpers.deny(interaction, _PARSE_HELP)
            return
        stdev = statistics.stdev(values) if len(values) >= 2 else 0.0
        body = (
            f"n={len(values)}\n"
            f"mean={statistics.mean(values):g}\n"
            f"median={statistics.median(values):g}\n"
            f"min={min(values):g}\n"
            f"max={max(values):g}\n"
            f"stdev={stdev:g}"
        )
        await helpers.send(interaction, helpers.clip(f"```\n{body}\n```"))

    @tree.command(name="quadratic", description="Real roots of ax^2 + bx + c.")
    @app_commands.describe(a="coefficient of x^2", b="coefficient of x", c="constant term")
    async def quadratic(interaction: Interaction, a: float, b: float, c: float) -> None:
        try:
            roots = _quadratic_roots(a, b, c)
        except ValueError as error:
            await helpers.send(interaction, str(error))
            return
        if len(roots) == 1:
            await helpers.send(interaction, f"linear root: x = {roots[0]:g}")
            return
        x1, x2 = roots
        await helpers.send(interaction, f"x1 = {x1:g}, x2 = {x2:g}")

    @tree.command(name="percent", description="Compute part as a percentage of whole.")
    @app_commands.describe(part="numerator", whole="denominator")
    async def percent(interaction: Interaction, part: float, whole: float) -> None:
        if whole == 0:
            await helpers.deny(interaction, "whole cannot be zero")
            return
        result = part / whole * 100
        await helpers.send(interaction, f"{part} is {result:g}% of {whole}")

    @tree.command(name="nthprime", description="Find the nth prime (1 <= n <= 10000).")
    @app_commands.describe(n="index (clamped to 1-10000)")
    async def nthprime(interaction: Interaction, n: int) -> None:
        if n < 1:
            await helpers.deny(interaction, "n must be at least 1")
            return
        clamped = _clamp(n, 1, _NTH_PRIME_MAX)
        await helpers.send(interaction, f"prime #{clamped} = {_nth_prime(clamped)}")

    @tree.command(name="collatz", description="Collatz steps required to reach 1.")
    @app_commands.describe(number="positive integer (clamped to 1-1,000,000,000)")
    async def collatz(interaction: Interaction, number: int) -> None:
        if number < 1:
            await helpers.deny(interaction, "give me a positive integer")
            return
        clamped = _clamp(number, 1, _COLLATZ_MAX)
        steps = _collatz_steps(clamped)
        await helpers.send(interaction, f"{clamped} reaches 1 in {steps} steps")

    @tree.command(name="average", description="Arithmetic mean of a list of numbers.")
    @app_commands.describe(numbers="comma- or space-separated numbers")
    async def average(interaction: Interaction, numbers: str) -> None:
        try:
            values = _parse_numbers(numbers)
        except ValueError:
            await helpers.deny(interaction, _PARSE_HELP)
            return
        await helpers.send(interaction, f"mean = {statistics.mean(values):g}")

    @tree.command(name="roundto", description="Round a number to a given number of digits.")
    @app_commands.describe(value="number to round", digits="decimal places (0-15, default 2)")
    async def round_to(interaction: Interaction, value: float, digits: int = 2) -> None:
        places = _clamp(digits, 0, _ROUND_DIGITS_MAX)
        await helpers.send(interaction, f"{value} rounded to {places} = {round(value, places)}")
