"""Public crypto market data from CoinGecko and alternative.me.

These endpoints expose live public market information only and are not
financial advice. Prices, ranks and indices may lag the underlying markets.
"""

from __future__ import annotations

from typing import Any

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_COINGECKO = "https://api.coingecko.com/api/v3"
_FEAR_GREED = "https://api.alternative.me/fng/"


def _fmt_money(value: float, currency: str) -> str:
    return f"{currency.upper()} {value:,.2f}"


async def _simple_price(coin: str, currency: str) -> tuple[float, float]:
    """Spot price and 24h percent change for one coin."""
    data = await helpers.fetch_json(
        f"{_COINGECKO}/simple/price",
        ids=coin,
        vs_currencies=currency,
        include_24hr_change="true",
    )
    bucket = data[coin]
    price = float(bucket[currency])
    change_raw = bucket.get(f"{currency}_24h_change", 0.0)
    try:
        change = float(change_raw)
    except (TypeError, ValueError):
        change = 0.0
    return price, change


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the public crypto market-data commands."""

    @tree.command(name="cryptoprice", description="Spot price for a coin in a fiat currency.")
    @app_commands.describe(coin="coin id like bitcoin", currency="fiat code like usd")
    async def cryptoprice(interaction: Interaction, coin: str, currency: str = "usd") -> None:
        await interaction.response.defer()
        coin_id = coin.strip().lower()
        cur = currency.strip().lower()
        try:
            price, change = await _simple_price(coin_id, cur)
        except Exception as error:
            logger.warning("cryptoprice failed: %s", error)
            await interaction.followup.send("couldn't fetch that price")
            return
        em = helpers.embed(coin_id, _fmt_money(price, cur))
        em.add_field(name="24h", value=f"{change:+.2f}%")
        await interaction.followup.send(embed=em)

    @tree.command(name="trending", description="Top trending coins on CoinGecko right now.")
    async def trending(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"{_COINGECKO}/search/trending")
            names = [str(coin["item"]["name"]) for coin in list(data["coins"])[:7]]
        except Exception as error:
            logger.warning("trending failed: %s", error)
            await interaction.followup.send("couldn't reach the trending feed")
            return
        body = "\n".join(f"- {name}" for name in names) or "no coins right now"
        await interaction.followup.send(embed=helpers.embed("Trending", helpers.clip(body)))

    @tree.command(name="coininfo", description="Summary for a single coin.")
    @app_commands.describe(coin="coin id like ethereum")
    async def coininfo(interaction: Interaction, coin: str) -> None:
        await interaction.response.defer()
        coin_id = coin.strip().lower()
        try:
            data = await helpers.fetch_json(f"{_COINGECKO}/coins/{coin_id}")
            market = data["market_data"]
            price = float(market["current_price"]["usd"])
            cap = float(market["market_cap"]["usd"])
        except Exception as error:
            logger.warning("coininfo failed: %s", error)
            await interaction.followup.send("couldn't find that coin")
            return
        em = helpers.embed(str(data.get("name") or coin_id))
        em.add_field(name="Rank", value=str(data.get("market_cap_rank") or "n/a"))
        em.add_field(name="Price", value=_fmt_money(price, "usd"))
        em.add_field(name="Market Cap", value=_fmt_money(cap, "usd"))
        await interaction.followup.send(embed=em)

    @tree.command(name="topcoins", description="Top 10 coins by market cap, in USD.")
    async def topcoins(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(
                f"{_COINGECKO}/coins/markets",
                vs_currency="usd",
                order="market_cap_desc",
                per_page=10,
                page=1,
            )
            lines: list[str] = []
            for entry in list(data)[:10]:
                name = entry.get("name") or entry.get("id") or "?"
                price = _fmt_money(float(entry["current_price"]), "usd")
                lines.append(f"- {name}: {price}")
        except Exception as error:
            logger.warning("topcoins failed: %s", error)
            await interaction.followup.send("couldn't reach the markets endpoint")
            return
        body = "\n".join(lines) or "no data"
        await interaction.followup.send(
            embed=helpers.embed("Top 10 by Market Cap", helpers.clip(body))
        )

    @tree.command(name="cryptoconvert", description="Convert a coin amount into a fiat currency.")
    @app_commands.describe(amount="coin amount", coin="coin id like bitcoin", currency="fiat code")
    async def cryptoconvert(
        interaction: Interaction, amount: float, coin: str, currency: str = "usd"
    ) -> None:
        await interaction.response.defer()
        coin_id = coin.strip().lower()
        cur = currency.strip().lower()
        try:
            price, _ = await _simple_price(coin_id, cur)
        except Exception as error:
            logger.warning("cryptoconvert failed: %s", error)
            await interaction.followup.send("couldn't fetch that price")
            return
        total = price * amount
        await interaction.followup.send(f"{amount} {coin_id} = {_fmt_money(total, cur)}")

    @tree.command(name="feargreed", description="Crypto Fear and Greed index from alternative.me.")
    async def feargreed(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(_FEAR_GREED)
            entry = data["data"][0]
            value = str(entry["value"])
            label = str(entry.get("value_classification") or "")
        except Exception as error:
            logger.warning("feargreed failed: %s", error)
            await interaction.followup.send("couldn't reach the index")
            return
        body = f"{value} ({label})" if label else value
        await interaction.followup.send(embed=helpers.embed("Fear & Greed Index", body))

    @tree.command(name="marketcap", description="Total USD market cap for one coin.")
    @app_commands.describe(coin="coin id like bitcoin")
    async def marketcap(interaction: Interaction, coin: str) -> None:
        await interaction.response.defer()
        coin_id = coin.strip().lower()
        try:
            data = await helpers.fetch_json(f"{_COINGECKO}/coins/{coin_id}")
            cap = float(data["market_data"]["market_cap"]["usd"])
        except Exception as error:
            logger.warning("marketcap failed: %s", error)
            await interaction.followup.send("couldn't find that coin")
            return
        await interaction.followup.send(
            embed=helpers.embed(str(data.get("name") or coin_id), _fmt_money(cap, "usd"))
        )
