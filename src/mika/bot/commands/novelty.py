"""Novelty commands: jokes, facts, advice, ratings, conversation prompts."""

from __future__ import annotations

import secrets
from typing import Any

import discord
from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_RPS_OPTIONS: tuple[str, ...] = ("rock", "paper", "scissors")
_RPS_BEATS: dict[str, str] = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

_WYR: tuple[tuple[str, str], ...] = (
    ("have the power of flight", "be invisible"),
    ("only eat sweet food forever", "only eat savory food forever"),
    ("live in a world with no music", "live in a world with no movies"),
    ("be able to read minds", "be able to time travel one hour back"),
    ("fight one horse-sized duck", "fight a hundred duck-sized horses"),
    ("never need to sleep", "never need to eat"),
    ("always be 10 minutes late", "always be 20 minutes early"),
    ("have unlimited free wifi anywhere", "have unlimited battery on every device"),
    ("speak every language fluently", "play every instrument flawlessly"),
    ("know how you will die", "know when you will die"),
    ("live without the internet for a year", "live without air conditioning for a year"),
    ("be famous but poor", "be rich but anonymous"),
)

_TOPICS: tuple[str, ...] = (
    "what's the best thing you ate this week?",
    "what's a hill you'll die on?",
    "what's the last show you binged?",
    "if you had to delete one social app, which one goes?",
    "weirdest job you'd consider for a million bucks?",
    "what's a small thing that always makes you happy?",
    "describe your dream vacation in five words.",
    "what's your most unpopular food opinion?",
    "first concert you ever went to?",
    "what's an underrated movie everyone should see?",
    "what app do you open without thinking?",
    "what's your most-used emoji and why?",
)

_QUESTIONS: tuple[str, ...] = (
    "what's a skill you wish you had?",
    "if you could live in any decade, which one?",
    "what's the worst trend from your childhood?",
    "what fictional world would you actually live in?",
    "what's the most useless talent you have?",
    "what would your villain origin story be?",
    "if pets could talk, which animal would be the rudest?",
    "what's a lie you've gotten away with?",
    "what's your go-to comfort meal?",
    "what hobby do you want to try this year?",
    "what song instantly puts you in a good mood?",
    "what's the weirdest thing you believed as a kid?",
)


def _bar(percent: int, width: int = 10) -> str:
    """A tiny text progress bar from a 0-100 percent value."""
    filled = round(percent / 100 * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the novelty commands."""

    @tree.command(name="joke", description="A random short joke.")
    async def joke(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://official-joke-api.appspot.com/random_joke")
            setup_line = str(data["setup"])
            punch = str(data["punchline"])
        except Exception as error:
            logger.warning("joke fetch failed: %s", error)
            await interaction.followup.send("couldn't fetch a joke right now")
            return
        await interaction.followup.send(helpers.clip(f"{setup_line}\n||{punch}||"))

    @tree.command(name="dadjoke", description="A groan-worthy dad joke.")
    async def dadjoke(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://icanhazdadjoke.com/slack")
            text = str(data["attachments"][0]["text"])
        except Exception as error:
            logger.warning("dadjoke fetch failed: %s", error)
            await interaction.followup.send("dad's out right now")
            return
        await interaction.followup.send(helpers.clip(text))

    @tree.command(name="advice", description="Unsolicited advice from a stranger.")
    async def advice(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://api.adviceslip.com/advice")
            text = str(data["slip"]["advice"])
        except Exception as error:
            logger.warning("advice fetch failed: %s", error)
            await interaction.followup.send("no advice today, sorry")
            return
        await interaction.followup.send(helpers.clip(text))

    @tree.command(name="catfact", description="A fact about cats.")
    async def catfact(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://catfact.ninja/fact")
            text = str(data["fact"])
        except Exception as error:
            logger.warning("catfact fetch failed: %s", error)
            await interaction.followup.send("the cats are quiet today")
            return
        await interaction.followup.send(helpers.clip(text))

    @tree.command(name="dogfact", description="A fact about dogs.")
    async def dogfact(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://dog-api.kinduff.com/api/facts")
            text = str(data["facts"][0])
        except Exception as error:
            logger.warning("dogfact fetch failed: %s", error)
            await interaction.followup.send("no dogs available for comment")
            return
        await interaction.followup.send(helpers.clip(text))

    @tree.command(name="numberfact", description="A fun fact about a number.")
    @app_commands.describe(number="the number to look up")
    async def numberfact(interaction: Interaction, number: int) -> None:
        await interaction.response.defer()
        try:
            text = await helpers.fetch_text(f"http://numbersapi.com/{number}")
        except Exception as error:
            logger.warning("numberfact fetch failed: %s", error)
            await interaction.followup.send("the numbers refuse to speak")
            return
        await interaction.followup.send(helpers.clip(text))

    @tree.command(name="kanye", description="A quote from Kanye West.")
    async def kanye(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://api.kanye.rest")
            text = str(data["quote"])
        except Exception as error:
            logger.warning("kanye fetch failed: %s", error)
            await interaction.followup.send("ye is unavailable")
            return
        await interaction.followup.send(helpers.clip(f"> {text}\n\u2014 Kanye West"))

    @tree.command(name="fact", description="A useless but true fact.")
    async def fact(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://uselessfacts.jsph.pl/api/v2/facts/random")
            text = str(data["text"])
        except Exception as error:
            logger.warning("fact fetch failed: %s", error)
            await interaction.followup.send("the trivia well is dry")
            return
        await interaction.followup.send(helpers.clip(text))

    @tree.command(name="affirmation", description="A kind word, on demand.")
    async def affirmation(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://www.affirmations.dev/")
            text = str(data["affirmation"])
        except Exception as error:
            logger.warning("affirmation fetch failed: %s", error)
            await interaction.followup.send("you are doing your best, and that counts")
            return
        await interaction.followup.send(helpers.clip(text))

    @tree.command(name="bored", description="An activity to kill boredom.")
    async def bored(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://bored-api.appbrewery.com/random")
            text = str(data["activity"])
        except Exception as error:
            logger.warning("bored fetch failed: %s", error)
            await interaction.followup.send("try staring at the ceiling for a bit")
            return
        await interaction.followup.send(helpers.clip(f"try this: {text}"))

    @tree.command(name="rps", description="Rock, paper, scissors against the bot.")
    @app_commands.describe(choice="rock, paper, or scissors")
    async def rps(interaction: Interaction, choice: str) -> None:
        user_choice = choice.strip().lower()
        if user_choice not in _RPS_BEATS:
            await helpers.send(interaction, "pick one of: rock, paper, scissors")
            return
        bot_choice = secrets.choice(_RPS_OPTIONS)
        if user_choice == bot_choice:
            result = "tie"
        elif _RPS_BEATS[user_choice] == bot_choice:
            result = "you win"
        else:
            result = "you lose"
        await helpers.send(
            interaction, f"you: {user_choice} \u2502 me: {bot_choice} \u2192 {result}"
        )

    @tree.command(name="iq", description="Measure someone's IQ. Totally accurate.")
    @app_commands.describe(user="whose IQ to measure (defaults to you)")
    async def iq(interaction: Interaction, user: discord.Member | None = None) -> None:
        target = helpers.target_user(interaction, user)
        score = secrets.randbelow(201)
        await helpers.send(interaction, f"{target.display_name}'s IQ: {score}")

    @tree.command(name="howgay", description="The official, definitely-scientific gay-meter.")
    @app_commands.describe(user="whose vibe to measure (defaults to you)")
    async def howgay(interaction: Interaction, user: discord.Member | None = None) -> None:
        target = helpers.target_user(interaction, user)
        percent = secrets.randbelow(101)
        await helpers.send(interaction, f"{target.display_name} is {percent}% gay {_bar(percent)}")

    @tree.command(name="rate", description="Rate a thing on a scale of 0 to 10.")
    @app_commands.describe(thing="what to rate")
    async def rate(interaction: Interaction, thing: str) -> None:
        score = secrets.randbelow(11)
        label = helpers.clip(thing.strip() or "that", 200)
        await helpers.send(interaction, f"i rate {label} a {score}/10")

    @tree.command(name="wyr", description="A random would-you-rather.")
    async def wyr(interaction: Interaction) -> None:
        left, right = secrets.choice(_WYR)
        await helpers.send(interaction, f"would you rather **{left}** or **{right}**?")

    @tree.command(name="topic", description="A random conversation starter.")
    async def topic(interaction: Interaction) -> None:
        await helpers.send(interaction, secrets.choice(_TOPICS))

    @tree.command(name="question", description="A random question to answer.")
    async def question(interaction: Interaction) -> None:
        await helpers.send(interaction, secrets.choice(_QUESTIONS))
