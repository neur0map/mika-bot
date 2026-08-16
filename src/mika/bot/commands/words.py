"""Word and language tools: synonyms, rhymes, spellcheck, scrabble, syllables."""

from __future__ import annotations

from typing import Any

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_DATAMUSE = "https://api.datamuse.com/words"
_LIMIT = 15
_FAIL = "couldn't reach the word service"

_SCRABBLE: dict[str, int] = {
    "a": 1,
    "e": 1,
    "i": 1,
    "l": 1,
    "n": 1,
    "o": 1,
    "r": 1,
    "s": 1,
    "t": 1,
    "u": 1,
    "d": 2,
    "g": 2,
    "b": 3,
    "c": 3,
    "m": 3,
    "p": 3,
    "f": 4,
    "h": 4,
    "v": 4,
    "w": 4,
    "y": 4,
    "k": 5,
    "j": 8,
    "x": 8,
    "q": 10,
    "z": 10,
}

_VOWELS = frozenset("aeiouy")


async def _datamuse_words(**params: Any) -> list[str]:
    """Call Datamuse and return up to _LIMIT word strings."""
    data = await helpers.fetch_json(_DATAMUSE, **params)
    words: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                word = item.get("word")
                if isinstance(word, str):
                    words.append(word)
            if len(words) >= _LIMIT:
                break
    return words


def _normalize_letters(text: str) -> str:
    return "".join(sorted(ch for ch in text.lower() if ch.isalpha()))


def _are_anagrams(first: str, second: str) -> bool:
    a = _normalize_letters(first)
    b = _normalize_letters(second)
    return bool(a) and a == b


def _scrabble_score(word: str) -> int:
    return sum(_SCRABBLE.get(ch, 0) for ch in word.lower())


def _syllable_count(word: str) -> int:
    cleaned = "".join(ch for ch in word.lower() if ch.isalpha())
    if not cleaned:
        return 0
    count = 0
    prev_vowel = False
    for ch in cleaned:
        is_vowel = ch in _VOWELS
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if cleaned.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


async def _send_words(
    interaction: Interaction, title: str, words: list[str], empty_note: str
) -> None:
    body = ", ".join(words) if words else empty_note
    await interaction.followup.send(embed=helpers.embed(title, helpers.clip(body)))


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the word and language commands."""

    @tree.command(name="synonyms", description="List synonyms for a word.")
    @app_commands.describe(word="word to look up")
    async def synonyms(interaction: Interaction, word: str) -> None:
        await interaction.response.defer()
        try:
            words = await _datamuse_words(rel_syn=word.strip())
            await _send_words(interaction, f"synonyms of {word}", words, "no synonyms found")
        except Exception as error:
            logger.warning("synonyms lookup failed: %s", error)
            await interaction.followup.send(_FAIL)

    @tree.command(name="antonyms", description="List antonyms for a word.")
    @app_commands.describe(word="word to look up")
    async def antonyms(interaction: Interaction, word: str) -> None:
        await interaction.response.defer()
        try:
            words = await _datamuse_words(rel_ant=word.strip())
            await _send_words(interaction, f"antonyms of {word}", words, "no antonyms found")
        except Exception as error:
            logger.warning("antonyms lookup failed: %s", error)
            await interaction.followup.send(_FAIL)

    @tree.command(name="rhymes", description="List words that rhyme with a word.")
    @app_commands.describe(word="word to rhyme with")
    async def rhymes(interaction: Interaction, word: str) -> None:
        await interaction.response.defer()
        try:
            words = await _datamuse_words(rel_rhy=word.strip())
            await _send_words(interaction, f"rhymes with {word}", words, "no rhymes found")
        except Exception as error:
            logger.warning("rhymes lookup failed: %s", error)
            await interaction.followup.send(_FAIL)

    @tree.command(name="soundslike", description="List words that sound like a word.")
    @app_commands.describe(word="word to match by sound")
    async def soundslike(interaction: Interaction, word: str) -> None:
        await interaction.response.defer()
        try:
            words = await _datamuse_words(sl=word.strip())
            await _send_words(interaction, f"sounds like {word}", words, "no matches found")
        except Exception as error:
            logger.warning("soundslike lookup failed: %s", error)
            await interaction.followup.send(_FAIL)

    @tree.command(name="related", description="List words related in meaning to a word.")
    @app_commands.describe(word="word to look up")
    async def related(interaction: Interaction, word: str) -> None:
        await interaction.response.defer()
        try:
            words = await _datamuse_words(ml=word.strip())
            await _send_words(interaction, f"related to {word}", words, "no related words found")
        except Exception as error:
            logger.warning("related lookup failed: %s", error)
            await interaction.followup.send(_FAIL)

    @tree.command(name="spellcheck", description="Suggest the closest spellings of a word.")
    @app_commands.describe(word="word to check")
    async def spellcheck(interaction: Interaction, word: str) -> None:
        await interaction.response.defer()
        try:
            words = await _datamuse_words(sp=word.strip())
            await _send_words(interaction, f"spellings near {word}", words, "no suggestions found")
        except Exception as error:
            logger.warning("spellcheck lookup failed: %s", error)
            await interaction.followup.send(_FAIL)

    @tree.command(name="startswith", description="List words that start with a prefix.")
    @app_commands.describe(prefix="leading letters to match")
    async def startswith(interaction: Interaction, prefix: str) -> None:
        await interaction.response.defer()
        try:
            words = await _datamuse_words(sp=f"{prefix.strip()}*")
            await _send_words(
                interaction, f"words starting with {prefix}", words, "no matches found"
            )
        except Exception as error:
            logger.warning("startswith lookup failed: %s", error)
            await interaction.followup.send(_FAIL)

    @tree.command(name="describe", description="List adjectives that describe a noun.")
    @app_commands.describe(noun="noun to describe")
    async def describe(interaction: Interaction, noun: str) -> None:
        await interaction.response.defer()
        try:
            words = await _datamuse_words(rel_jjb=noun.strip())
            await _send_words(interaction, f"adjectives for {noun}", words, "no descriptors found")
        except Exception as error:
            logger.warning("describe lookup failed: %s", error)
            await interaction.followup.send(_FAIL)

    @tree.command(name="anagram", description="Check whether two words are anagrams.")
    @app_commands.describe(first="first word", second="second word")
    async def anagram(interaction: Interaction, first: str, second: str) -> None:
        if _are_anagrams(first, second):
            await helpers.send(interaction, f"{first} and {second} are anagrams")
        else:
            await helpers.send(interaction, f"{first} and {second} are not anagrams")

    @tree.command(name="scrabble", description="Score a word using standard Scrabble values.")
    @app_commands.describe(word="word to score")
    async def scrabble(interaction: Interaction, word: str) -> None:
        score = _scrabble_score(word)
        await helpers.send(interaction, f"{word} is worth {score} points in Scrabble")

    @tree.command(name="syllables", description="Estimate the syllable count of a word.")
    @app_commands.describe(word="word to analyze")
    async def syllables(interaction: Interaction, word: str) -> None:
        count = _syllable_count(word)
        label = "syllable" if count == 1 else "syllables"
        await helpers.send(interaction, f"{word} has about {count} {label}")
