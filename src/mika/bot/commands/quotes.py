"""Quotes and jokes: wisdom, motivation, insults, compliments and shower thoughts."""

from __future__ import annotations

import secrets
from typing import Any

import discord
from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_FORTUNES: tuple[str, ...] = (
    "a pleasant surprise is waiting for you.",
    "the early bird gets the worm, but the second mouse gets the cheese.",
    "your hard work is about to pay off. remember, dreams are the seeds of reality.",
    "you will travel to many exotic places in your lifetime.",
    "today is a good day to try something new.",
    "an old friend will reach out to you soon.",
    "the answer you seek is closer than you think.",
    "small steps in the right direction can turn out to be the biggest step of your life.",
    "good news will come to you by mail.",
    "trust your instincts. they are usually right.",
    "your kindness will lead you to success.",
    "patience is your ally today.",
    "a thrilling time is in your immediate future.",
    "fortune favors the brave \u2014 but also the well-prepared.",
    "the road to success is always under construction.",
    "you will find a hidden treasure where you least expect it.",
    "a smile is your personal welcome mat.",
    "the project you have in mind will soon move ahead.",
    "do not be afraid of competition; you are the competition.",
    "happiness begins with facing life with a smile and a wink.",
)

_PICKUPS: tuple[str, ...] = (
    "are you a wifi signal? because i'm feeling a connection.",
    "are you a parking ticket? because you've got 'fine' written all over you.",
    "if you were a vegetable, you'd be a cute-cumber.",
    "do you have a map? i keep getting lost in your eyes.",
    "is your name google? because you have everything i've been searching for.",
    "are you made of copper and tellurium? because you're Cu-Te.",
    "if beauty were time, you'd be an eternity.",
    "do you believe in love at first sight, or should i walk by again?",
    "are you a magician? because whenever i look at you, everyone else disappears.",
    "i must be a snowflake, because i've fallen for you.",
    "is your dad a baker? because you're a cutie pie.",
    "do you have a name, or can i call you mine?",
    "are you a campfire? because you're hot and i want s'more.",
    "if i could rearrange the alphabet, i'd put u and i together.",
    "are you french? because madame-oiselle.",
    "is there an airport nearby, or is that just my heart taking off?",
    "do you have a bandage? because i just scraped my knee falling for you.",
    "your hand looks heavy \u2014 let me hold it for you.",
    "are you a time traveler? because i can see you in my future.",
    "i was blinded by your beauty \u2014 i'll need your name and number for insurance.",
)

_ROASTS: tuple[str, ...] = (
    "you bring everyone so much joy \u2014 when you leave the room.",
    "you have the perfect face for radio.",
    "if i wanted to hear from someone like you, i'd watch a yogurt commercial.",
    "you're not stupid; you just have bad luck thinking.",
    "i'd agree with you, but then we'd both be wrong.",
    "you have something on your chin \u2026 no, the third one down.",
    "your secrets are always safe with me \u2014 i never even listen when you tell them.",
    "i'm jealous of all the people who haven't met you yet.",
    "you're proof that even evolution takes a coffee break.",
    "you're the reason shampoo bottles have instructions.",
    "you have a face only a mother could photoshop.",
    "if laughter is the best medicine, your face must be curing the world.",
    "you're like a software update \u2014 every time i see you, i think 'not now.'",
    "you have a head start in every race because you're already behind.",
    "you bring everyone together \u2026 to talk about you.",
    "your spirit animal is a participation trophy.",
    "you're not the dumbest person on earth, but you'd better hope they don't die.",
    "i'd explain it to you, but i left my crayons at home.",
    "you have the charm of a wet sock.",
    "you're the human equivalent of a typo.",
)

_WISDOM: tuple[str, ...] = (
    "fall seven times, stand up eight.",
    "a journey of a thousand miles begins with a single step.",
    "do not wait to strike till the iron is hot, but make it hot by striking.",
    "the best time to plant a tree was twenty years ago. the second-best time is now.",
    "what you do speaks so loudly that i cannot hear what you say.",
    "the only true wisdom is in knowing you know nothing.",
    "an ounce of prevention is worth a pound of cure.",
    "still waters run deep.",
    "a smooth sea never made a skilled sailor.",
    "you cannot cross the sea merely by standing and staring at the water.",
    "patience is bitter, but its fruit is sweet.",
    "where there is no struggle, there is no strength.",
    "he who has a why to live can bear almost any how.",
    "the obstacle is the path.",
    "the cave you fear to enter holds the treasure you seek.",
    "what does not kill us makes us stronger.",
    "the wound is the place where the light enters you.",
    "comparison is the thief of joy.",
    "first do it, then do it right, then do it better.",
    "the man who moves a mountain begins by carrying away small stones.",
)


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the quotes and jokes commands."""

    @tree.command(name="quote", description="A random thoughtful quote.")
    async def quote(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://api.quotable.io/random")
            text = str(data["content"])
            author = str(data["author"])
        except Exception as error:
            logger.warning("quote fetch failed: %s", error)
            await interaction.followup.send(f"> {secrets.choice(_WISDOM)}\n\u2014 unknown")
            return
        await interaction.followup.send(helpers.clip(f"> {text}\n\u2014 {author}"))

    @tree.command(name="chucknorris", description="A Chuck Norris fact.")
    async def chucknorris(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://api.chucknorris.io/jokes/random")
            text = str(data["value"])
        except Exception as error:
            logger.warning("chucknorris fetch failed: %s", error)
            await interaction.followup.send("chuck is too busy roundhouse-kicking the api.")
            return
        await interaction.followup.send(helpers.clip(text))

    @tree.command(name="insult", description="A playful insult, with love.")
    async def insult(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(
                "https://evilinsult.com/generate_insult.php", lang="en", type="json"
            )
            text = str(data["insult"])
        except Exception as error:
            logger.warning("insult fetch failed: %s", error)
            text = secrets.choice(_ROASTS)
        await interaction.followup.send(helpers.clip(text))

    @tree.command(name="compliment", description="A small daily compliment.")
    async def compliment(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://complimentr.com/api")
            text = str(data["compliment"])
        except Exception as error:
            logger.warning("compliment fetch failed: %s", error)
            await interaction.followup.send("you are exactly the right amount of you.")
            return
        await interaction.followup.send(helpers.clip(text))

    @tree.command(name="motivate", description="A motivational quote of the day.")
    async def motivate(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://zenquotes.io/api/random")
            text = str(data[0]["q"])
            author = str(data[0]["a"])
        except Exception as error:
            logger.warning("motivate fetch failed: %s", error)
            await interaction.followup.send(f"> {secrets.choice(_WISDOM)}\n\u2014 unknown")
            return
        await interaction.followup.send(helpers.clip(f"> {text}\n\u2014 {author}"))

    @tree.command(name="yomama", description="A yo-mama joke.")
    async def yomama(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://www.yomama-jokes.com/api/v1/jokes/random/")
            text = str(data["joke"])
        except Exception as error:
            logger.warning("yomama fetch failed: %s", error)
            await interaction.followup.send("yo mama so kind she taught me to fail gracefully.")
            return
        await interaction.followup.send(helpers.clip(text))

    @tree.command(name="showerthought", description="A top shower thought from today.")
    async def showerthought(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(
                "https://www.reddit.com/r/showerthoughts/top.json", limit=1, t="day"
            )
            text = str(data["data"]["children"][0]["data"]["title"])
        except Exception as error:
            logger.warning("showerthought fetch failed: %s", error)
            text = secrets.choice(_WISDOM)
        await interaction.followup.send(helpers.clip(text))

    @tree.command(name="geek", description="A geeky one-liner.")
    async def geek(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(
                "https://geek-jokes.sameerkumar.website/api", format="json"
            )
            text = str(data["joke"])
        except Exception as error:
            logger.warning("geek fetch failed: %s", error)
            await interaction.followup.send("there are 10 kinds of people: those who get binary.")
            return
        await interaction.followup.send(helpers.clip(text))

    @tree.command(name="fortune", description="A fortune-cookie line.")
    async def fortune(interaction: Interaction) -> None:
        await helpers.send(interaction, secrets.choice(_FORTUNES))

    @tree.command(name="pickup", description="A cheesy pickup line.")
    async def pickup(interaction: Interaction) -> None:
        await helpers.send(interaction, secrets.choice(_PICKUPS))

    @tree.command(name="roast", description="A playful roast for someone.")
    @app_commands.describe(user="whom to roast (defaults to you)")
    async def roast(interaction: Interaction, user: discord.Member | None = None) -> None:
        target = helpers.target_user(interaction, user)
        line = secrets.choice(_ROASTS)
        await helpers.send(interaction, f"{target.mention} {line}")

    @tree.command(name="wisdom", description="A bit of timeless wisdom.")
    async def wisdom(interaction: Interaction) -> None:
        await helpers.send(interaction, secrets.choice(_WISDOM))
