"""Game commands: trivia, dice, slots, riddles, prompts and quick coin duels."""

from __future__ import annotations

import html
import re
import secrets
from typing import Any

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)


_DICE_RE = re.compile(r"^\s*(\d+)\s*d\s*(\d+)\s*$", re.IGNORECASE)
_DICE_MAX_COUNT = 20
_DICE_MAX_SIDES = 1000
_GUESS_MAX = 10
_LOTTERY_PICKS = 6
_LOTTERY_MAX = 49
_SCRAMBLE_TRIES = 8

_SLOT_REELS: tuple[str, ...] = (
    "\U0001f352",
    "\U0001f34b",
    "\U0001f347",
    "\u2b50",
    "\U0001f48e",
    "\U0001f514",
)

_SCRAMBLE_WORDS: tuple[str, ...] = (
    "python",
    "discord",
    "guitar",
    "rainbow",
    "puzzle",
    "library",
    "marshmallow",
    "telescope",
    "elephant",
    "keyboard",
    "chocolate",
    "umbrella",
    "submarine",
    "saxophone",
    "blueberry",
    "asteroid",
    "labyrinth",
    "carnival",
    "dolphin",
    "harmonica",
    "pineapple",
    "volcano",
    "kangaroo",
    "mountain",
)

_TRUTHS: tuple[str, ...] = (
    "what's the most embarrassing song on your playlist?",
    "what's a lie you tell yourself often?",
    "who in this server would you trust with a secret?",
    "what's the worst gift you've ever received?",
    "what's something you've never told your parents?",
    "what's your weirdest habit?",
    "have you ever pretended to like a gift you hated?",
    "what's the longest you've gone without sleep?",
    "what's the dumbest thing you've cried over?",
    "what's a crush you'd never admit to in person?",
    "what's the last thing you googled?",
    "what's a compliment you secretly enjoyed too much?",
)

_DARES: tuple[str, ...] = (
    "send the last picture in your camera roll to the next person to message.",
    "change your nickname to something silly for the next hour.",
    "type only in uppercase for the next ten minutes.",
    "send a voice clip humming your favourite chorus.",
    "post the most recent meme you saved.",
    "set your status to a haiku you wrote on the spot.",
    "compliment three people in the server.",
    "react to ten messages with the same random emoji.",
    "tell a joke and own the silence afterwards.",
    "explain your most-used emoji as if it were a dissertation.",
    "speak in third person for the next five messages.",
    "post a screenshot of your home screen.",
)

_NHIE: tuple[str, ...] = (
    "never have i ever fallen asleep in a movie theatre.",
    "never have i ever lied to get out of plans.",
    "never have i ever pretended to know a song i had never heard.",
    "never have i ever ghosted a group chat.",
    "never have i ever broken a bone.",
    "never have i ever stayed up an entire night for no reason.",
    "never have i ever sent a text to the wrong person.",
    "never have i ever cried at a commercial.",
    "never have i ever forgotten someone's name mid-conversation.",
    "never have i ever eaten cereal for dinner.",
    "never have i ever rage-quit a game.",
    "never have i ever talked to myself out loud in public.",
)

_WYR: tuple[tuple[str, str], ...] = (
    ("explore the deep ocean", "explore deep space"),
    ("be fluent in every language", "master every instrument"),
    ("have a photographic memory", "be able to forget anything on demand"),
    ("live one year in the past", "live one year in the future"),
    ("always tell the truth", "never need to sleep again"),
    ("be the funniest person in the room", "be the smartest person in the room"),
    ("control fire", "control water"),
    ("be invisible at will", "teleport once a day"),
    (
        "re-read your favourite book for the first time",
        "re-watch your favourite film for the first time",
    ),
    ("have unlimited cheap pizza", "have unlimited cheap sushi"),
    ("live without music for a year", "live without video for a year"),
    ("know every language", "know every recipe"),
)

_RIDDLE_FALLBACK: tuple[tuple[str, str], ...] = (
    ("what has to be broken before you can use it?", "an egg"),
    ("the more of this there is, the less you see. what is it?", "darkness"),
    ("what has many keys but can't open a single lock?", "a piano"),
    ("what runs but never walks, has a mouth but never speaks?", "a river"),
    ("what gets wetter the more it dries?", "a towel"),
)


def _shuffle[T](items: list[T]) -> list[T]:
    out = list(items)
    for i in range(len(out) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def _scramble_word(word: str) -> str:
    letters = list(word)
    for _ in range(_SCRAMBLE_TRIES):
        letters = _shuffle(letters)
        if "".join(letters) != word:
            break
    return "".join(letters)


def _parse_dice(notation: str) -> tuple[int, int] | None:
    """Parse NdM into (count, sides), clamped; None on garbage."""
    match = _DICE_RE.match(notation)
    if not match:
        return None
    count = int(match.group(1))
    sides = int(match.group(2))
    if count < 1 or sides < 2:
        return None
    return min(count, _DICE_MAX_COUNT), min(sides, _DICE_MAX_SIDES)


def _lottery_pick() -> list[int]:
    picks: set[int] = set()
    while len(picks) < _LOTTERY_PICKS:
        picks.add(secrets.randbelow(_LOTTERY_MAX) + 1)
    return sorted(picks)


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the game commands."""

    @tree.command(name="trivia", description="A multiple-choice trivia question.")
    async def trivia(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://opentdb.com/api.php?amount=1&type=multiple")
            entry = data["results"][0]
            question = html.unescape(str(entry["question"]))
            correct = html.unescape(str(entry["correct_answer"]))
            options = [html.unescape(str(opt)) for opt in entry["incorrect_answers"]]
            options.append(correct)
        except Exception as error:
            logger.warning("trivia fetch failed: %s", error)
            await interaction.followup.send("the trivia gods are silent right now")
            return
        shuffled = _shuffle(options)
        lines = [f"**{question}**"]
        for i, option in enumerate(shuffled):
            lines.append(f"{chr(65 + i)}. {option}")
        lines.append(f"answer: ||{correct}||")
        await interaction.followup.send(helpers.clip("\n".join(lines)))

    @tree.command(name="roll", description="Roll dice in NdM notation (e.g. 2d20).")
    @app_commands.describe(dice="dice notation like 1d6 or 3d20")
    async def roll(interaction: Interaction, dice: str = "1d6") -> None:
        parsed = _parse_dice(dice)
        if parsed is None:
            await helpers.send(interaction, "couldn't read that dice. try `2d6` or `1d20`")
            return
        count, sides = parsed
        rolls = [secrets.randbelow(sides) + 1 for _ in range(count)]
        joined = ", ".join(str(r) for r in rolls)
        await helpers.send(interaction, f"{count}d{sides}: [{joined}] = **{sum(rolls)}**")

    @tree.command(name="guess", description="Guess a number from 1 to 10.")
    @app_commands.describe(guess="your guess between 1 and 10")
    async def guess_cmd(interaction: Interaction, guess: int) -> None:
        secret = secrets.randbelow(_GUESS_MAX) + 1
        if guess == secret:
            await helpers.send(interaction, f"yes! it was **{secret}**. you nailed it.")
        else:
            await helpers.send(
                interaction,
                f"nope, it was **{secret}**. you guessed **{guess}**.",
            )

    @tree.command(name="slots", description="Spin the slot machine.")
    async def slots(interaction: Interaction) -> None:
        reels = [secrets.choice(_SLOT_REELS) for _ in range(3)]
        line = " | ".join(reels)
        if reels[0] == reels[1] == reels[2]:
            result = "jackpot! all three match."
        else:
            result = "no luck. spin again?"
        await helpers.send(interaction, f"[ {line} ]\n{result}")

    @tree.command(name="scramble", description="Unscramble the hidden word.")
    async def scramble(interaction: Interaction) -> None:
        word = secrets.choice(_SCRAMBLE_WORDS)
        scrambled = _scramble_word(word)
        await helpers.send(interaction, f"unscramble this: **{scrambled}**\nanswer: ||{word}||")

    @tree.command(name="riddle", description="A riddle, answer hidden in a spoiler.")
    async def riddle(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json("https://riddles-api.vercel.app/random")
            question = str(data["riddle"])
            answer = str(data["answer"])
        except Exception as error:
            logger.warning("riddle fetch failed: %s", error)
            question, answer = secrets.choice(_RIDDLE_FALLBACK)
        await interaction.followup.send(helpers.clip(f"{question}\nanswer: ||{answer}||"))

    @tree.command(name="truthordare", description="Pick a truth or a dare.")
    @app_commands.describe(mode="`truth` or `dare`")
    async def truthordare(interaction: Interaction, mode: str = "truth") -> None:
        choice = mode.strip().lower()
        if choice not in ("truth", "dare"):
            await helpers.send(interaction, "pick `truth` or `dare`")
            return
        pool = _TRUTHS if choice == "truth" else _DARES
        await helpers.send(interaction, f"**{choice}:** {secrets.choice(pool)}")

    @tree.command(name="neverhaveiever", description="A never-have-i-ever prompt.")
    async def neverhaveiever(interaction: Interaction) -> None:
        await helpers.send(interaction, secrets.choice(_NHIE))

    @tree.command(name="wouldyourather", description="A would-you-rather dilemma.")
    async def wouldyourather(interaction: Interaction) -> None:
        left, right = secrets.choice(_WYR)
        await helpers.send(interaction, f"would you rather **{left}** or **{right}**?")

    @tree.command(name="lottery", description="Six lucky numbers between 1 and 49.")
    async def lottery(interaction: Interaction) -> None:
        picks = _lottery_pick()
        joined = ", ".join(str(n) for n in picks)
        await helpers.send(interaction, f"your lucky numbers: {joined}")

    @tree.command(name="coinduel", description="Flip a coin between two named sides.")
    @app_commands.describe(side_a="first side", side_b="second side")
    async def coinduel(interaction: Interaction, side_a: str, side_b: str) -> None:
        winner = secrets.choice((side_a, side_b))
        await helpers.send(interaction, f"{side_a} vs {side_b} \u2192 winner: **{winner}**")
