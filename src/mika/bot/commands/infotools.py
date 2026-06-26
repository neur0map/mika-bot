"""Info and utility commands: server/channel/role details and quick lookups."""

from __future__ import annotations

from typing import Any

import discord
from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_HEX = set("0123456789abcdefABCDEF")


def _no_guild(interaction: Interaction) -> bool:
    return interaction.guild is None


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the info/utility commands."""

    @tree.command(name="channelinfo", description="Show details about a text channel.")
    @app_commands.describe(channel="the channel (defaults to here)")
    async def channelinfo(
        interaction: Interaction, channel: discord.TextChannel | None = None
    ) -> None:
        target: Any = channel or interaction.channel
        if target is None:
            await helpers.deny(interaction, "no channel here")
            return
        emb = helpers.embed(title=f"#{getattr(target, 'name', 'channel')}")
        emb.add_field(name="ID", value=str(getattr(target, "id", "?")))
        created = getattr(target, "created_at", None)
        emb.add_field(
            name="Created",
            value=discord.utils.format_dt(created, "R") if created else "unknown",
        )
        is_nsfw = getattr(target, "is_nsfw", None)
        emb.add_field(name="NSFW", value=str(bool(is_nsfw()) if callable(is_nsfw) else False))
        topic = getattr(target, "topic", None)
        if isinstance(topic, str) and topic:
            emb.add_field(name="Topic", value=helpers.clip(topic, 200), inline=False)
        await helpers.send(interaction, embed=emb)

    @tree.command(name="roleinfo", description="Show details about a role.")
    @app_commands.describe(role="the role to inspect")
    async def roleinfo(interaction: Interaction, role: discord.Role) -> None:
        emb = helpers.embed(title=role.name)
        emb.add_field(name="ID", value=str(role.id))
        emb.add_field(name="Color", value=str(role.color))
        emb.add_field(name="Position", value=str(role.position))
        emb.add_field(name="Mention", value=role.mention)
        await helpers.send(interaction, embed=emb)

    @tree.command(name="emojiinfo", description="Echo an emoji and its raw form.")
    @app_commands.describe(emoji="the emoji or string")
    async def emojiinfo(interaction: Interaction, emoji: str) -> None:
        emb = helpers.embed(title="emoji")
        emb.add_field(name="Value", value=helpers.clip(emoji, 200) or "?")
        emb.add_field(name="Length", value=str(len(emoji)))
        await helpers.send(interaction, embed=emb)

    @tree.command(name="serverroles", description="List every role in this server.")
    async def serverroles(interaction: Interaction) -> None:
        if _no_guild(interaction):
            await helpers.deny(interaction, "use this inside a server")
            return
        guild = interaction.guild
        assert guild is not None
        names = [role.name for role in guild.roles]
        await helpers.send(interaction, helpers.clip(", ".join(names) or "no roles"))

    @tree.command(name="serverchannels", description="List every channel in this server.")
    async def serverchannels(interaction: Interaction) -> None:
        if _no_guild(interaction):
            await helpers.deny(interaction, "use this inside a server")
            return
        guild = interaction.guild
        assert guild is not None
        channels: Any = getattr(guild, "channels", []) or []
        names = [getattr(c, "name", "?") for c in channels]
        await helpers.send(interaction, helpers.clip(", ".join(names) or "no channels"))

    @tree.command(name="membercount", description="Show the server's member count.")
    async def membercount(interaction: Interaction) -> None:
        if _no_guild(interaction):
            await helpers.deny(interaction, "use this inside a server")
            return
        guild = interaction.guild
        assert guild is not None
        await helpers.send(interaction, f"{guild.member_count} members")

    @tree.command(name="boosts", description="Show how many boosts the server has.")
    async def boosts(interaction: Interaction) -> None:
        if _no_guild(interaction):
            await helpers.deny(interaction, "use this inside a server")
            return
        guild = interaction.guild
        assert guild is not None
        await helpers.send(interaction, f"{guild.premium_subscription_count} boosts")

    @tree.command(name="servericon", description="Show the server's icon.")
    async def servericon(interaction: Interaction) -> None:
        if _no_guild(interaction):
            await helpers.deny(interaction, "use this inside a server")
            return
        guild = interaction.guild
        assert guild is not None
        if guild.icon is None:
            await helpers.send(interaction, "no icon set")
            return
        await helpers.send(interaction, guild.icon.url)

    @tree.command(name="serverbanner", description="Show the server's banner.")
    async def serverbanner(interaction: Interaction) -> None:
        if _no_guild(interaction):
            await helpers.deny(interaction, "use this inside a server")
            return
        guild = interaction.guild
        assert guild is not None
        if guild.banner is None:
            await helpers.send(interaction, "no banner set")
            return
        await helpers.send(interaction, guild.banner.url)

    @tree.command(name="weather", description="Current weather for a city.")
    @app_commands.describe(city="city name, e.g. london")
    async def weather(interaction: Interaction, city: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"https://wttr.in/{city}?format=j1")
            current = data["current_condition"][0]
            temp = current["temp_C"]
            desc = current["weatherDesc"][0]["value"]
        except Exception as error:
            logger.warning("weather fetch failed: %s", error)
            await interaction.followup.send("couldn't fetch the weather right now")
            return
        await interaction.followup.send(f"{city}: {temp}\u00b0C, {desc}")

    @tree.command(name="urban", description="Look up a term on Urban Dictionary.")
    @app_commands.describe(term="word or phrase to define")
    async def urban(interaction: Interaction, term: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(
                f"https://api.urbandictionary.com/v0/define?term={term}"
            )
            entries = data["list"]
            if not entries:
                await interaction.followup.send("no definitions found")
                return
            definition = str(entries[0]["definition"])
        except Exception as error:
            logger.warning("urban fetch failed: %s", error)
            await interaction.followup.send("couldn't reach urban dictionary right now")
            return
        await interaction.followup.send(helpers.clip(definition) or "no definitions found")

    @tree.command(name="define", description="Dictionary definition of a word.")
    @app_commands.describe(word="english word")
    async def define(interaction: Interaction, word: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(
                f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
            )
            definition = str(data[0]["meanings"][0]["definitions"][0]["definition"])
        except Exception as error:
            logger.warning("define fetch failed: %s", error)
            await interaction.followup.send("couldn't find that word")
            return
        await interaction.followup.send(helpers.clip(f"**{word}**: {definition}"))

    @tree.command(name="crypto", description="Current USD price of a coin.")
    @app_commands.describe(coin="coin id, e.g. bitcoin")
    async def crypto(interaction: Interaction, coin: str) -> None:
        await interaction.response.defer()
        key = coin.lower()
        try:
            data = await helpers.fetch_json(
                f"https://api.coingecko.com/api/v3/simple/price?ids={key}&vs_currencies=usd"
            )
            price = data[key]["usd"]
        except Exception as error:
            logger.warning("crypto fetch failed: %s", error)
            await interaction.followup.send("couldn't fetch the price right now")
            return
        await interaction.followup.send(f"{key}: ${price} USD")

    @tree.command(name="wikipedia", description="Wikipedia summary for a topic.")
    @app_commands.describe(query="topic to look up")
    async def wikipedia(interaction: Interaction, query: str) -> None:
        await interaction.response.defer()
        slug = query.strip().replace(" ", "_")
        try:
            data = await helpers.fetch_json(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
            )
            extract = str(data["extract"])
        except Exception as error:
            logger.warning("wikipedia fetch failed: %s", error)
            await interaction.followup.send("couldn't reach wikipedia right now")
            return
        await interaction.followup.send(helpers.clip(extract) or "no summary available")

    @tree.command(name="color", description="Preview a #RRGGBB color.")
    @app_commands.describe(hex_code="hex code like #ff8800")
    async def color(interaction: Interaction, hex_code: str) -> None:
        raw = hex_code.strip().lstrip("#")
        if len(raw) != 6 or any(ch not in _HEX for ch in raw):
            await helpers.deny(interaction, "give me a #RRGGBB hex code")
            return
        value = int(raw, 16)
        r, g, b = (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF
        emb = discord.Embed(
            title=f"#{raw.lower()}",
            description=f"R={r} G={g} B={b}",
            color=discord.Color(value),
        )
        await helpers.send(interaction, embed=emb)
