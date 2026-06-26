"""Text transforms: reverse, leet, owo, morse, base64, binary/hex and friends."""

from __future__ import annotations

import base64
import binascii
import codecs
import secrets
from collections.abc import Callable
from typing import Any

import pyfiglet
from discord import Interaction, app_commands

from mika.bot.commands import helpers

_CAP = 400

_FLIP = {
    "a": "\u0250",
    "b": "q",
    "c": "\u0254",
    "d": "p",
    "e": "\u01dd",
    "f": "\u025f",
    "g": "\u0183",
    "h": "\u0265",
    "i": "\u0131",
    "j": "\u027e",
    "k": "\u029e",
    "m": "\u026f",
    "n": "u",
    "p": "d",
    "q": "b",
    "r": "\u0279",
    "t": "\u0287",
    "u": "n",
    "v": "\u028c",
    "w": "\u028d",
    "y": "\u028e",
    "?": "\u00bf",
    "!": "\u00a1",
    ".": "\u02d9",
    "'": ",",
    "(": ")",
    ")": "(",
    "[": "]",
    "]": "[",
}
_LEET = str.maketrans("aeiostlAEIOSTL", "43105714310571")
_MORSE = {
    "a": ".-",
    "b": "-...",
    "c": "-.-.",
    "d": "-..",
    "e": ".",
    "f": "..-.",
    "g": "--.",
    "h": "....",
    "i": "..",
    "j": ".---",
    "k": "-.-",
    "l": ".-..",
    "m": "--",
    "n": "-.",
    "o": "---",
    "p": ".--.",
    "q": "--.-",
    "r": ".-.",
    "s": "...",
    "t": "-",
    "u": "..-",
    "v": "...-",
    "w": ".--",
    "x": "-..-",
    "y": "-.--",
    "z": "--..",
    "0": "-----",
    "1": ".----",
    "2": "..---",
    "3": "...--",
    "4": "....-",
    "5": ".....",
    "6": "-....",
    "7": "--...",
    "8": "---..",
    "9": "----.",
    " ": "/",
}
_ZALGO = [chr(code) for code in range(0x0300, 0x0316)]


def _upsidedown(text: str) -> str:
    return "".join(_FLIP.get(c, c) for c in text.lower())[::-1]


def _owo(text: str) -> str:
    swapped = text.translate(str.maketrans("rlRL", "wwWW"))
    return f"{swapped} owo"


def _spoiler(text: str) -> str:
    return "".join(f"||{c}||" for c in text[:_CAP])


def _regional(text: str) -> str:
    out: list[str] = []
    for char in text[:_CAP].lower():
        if "a" <= char <= "z":
            out.append(chr(0x1F1E6 + ord(char) - 97) + " ")
        else:
            out.append("  " if char == " " else char)
    return "".join(out)


def _vape(text: str) -> str:
    out: list[str] = []
    for char in text[:_CAP]:
        if char == " ":
            out.append("\u3000")
        elif "!" <= char <= "~":
            out.append(chr(ord(char) + 0xFEE0))
        else:
            out.append(char)
    return "".join(out)


def _smart(text: str) -> str:
    return "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(text))


def _zalgo(text: str) -> str:
    out: list[str] = []
    for char in text[:_CAP]:
        out.append(char)
        out.extend(secrets.choice(_ZALGO) for _ in range(secrets.randbelow(4) + 1))
    return "".join(out)


def _rot13(text: str) -> str:
    return str(codecs.encode(text, "rot13"))


def _b64encode(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _b64decode(text: str) -> str:
    try:
        return base64.b64decode(text.encode(), validate=True).decode()
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return "couldn't decode that"


def _bin2text(text: str) -> str:
    try:
        return "".join(chr(int(group, 2)) for group in text.split())
    except ValueError:
        return "couldn't read that binary"


def _hex2text(text: str) -> str:
    try:
        return bytes.fromhex(text.replace(" ", "")).decode()
    except (ValueError, UnicodeDecodeError):
        return "couldn't read that hex"


def _ascii_art(text: str) -> str:
    return f"```\n{pyfiglet.figlet_format(text[:20])}\n```"


_TRANSFORMS: list[tuple[str, str, Callable[[str], str]]] = [
    ("reverse", "Reverse your text.", lambda t: t[::-1]),
    ("upsidedown", "Flip your text upside down.", _upsidedown),
    ("smart", "AlTeRnAtInG caps.", _smart),
    ("1337", "Leetspeak your text.", lambda t: t.translate(_LEET)),
    ("owo", "OwO-ify your text.", _owo),
    ("regional", "Text as regional-indicator emoji.", _regional),
    ("space", "S p a c e d   o u t.", lambda t: " ".join(t[:_CAP])),
    ("vape", "Fullwidth vaporwave text.", _vape),
    ("spoiler", "Hide every character behind a spoiler.", _spoiler),
    ("italic", "Italicise your text.", lambda t: f"*{t}*"),
    ("zalgo", "Cursed zalgo text.", _zalgo),
    (
        "morse",
        "Translate text to morse code.",
        lambda t: " ".join(_MORSE.get(c, c) for c in t.lower()),
    ),
    ("semoji", "Sparkles between every word.", lambda t: " \u2728 ".join(t.split())),
    ("codeblock", "Wrap text in a code block.", lambda t: f"```\n{t}\n```"),
    ("encode", "Encode text to base64.", _b64encode),
    ("decode", "Decode base64 text.", _b64decode),
    ("encrypt", "Encrypt text with rot13.", _rot13),
    ("decrypt", "Decrypt rot13 text.", _rot13),
    ("ascii", "Turn text into ASCII art.", _ascii_art),
    ("text2bin", "Text to binary.", lambda t: " ".join(format(ord(c), "08b") for c in t[:_CAP])),
    ("bin2text", "Binary to text.", _bin2text),
    ("text2hex", "Text to hexadecimal.", lambda t: t.encode().hex()),
    ("hex2text", "Hexadecimal to text.", _hex2text),
]


def _register(
    tree: app_commands.CommandTree[Any], name: str, desc: str, fn: Callable[[str], str]
) -> None:
    @tree.command(name=name, description=desc)
    @app_commands.describe(text="the text to transform")
    async def command(interaction: Interaction, text: str) -> None:
        await helpers.send(interaction, helpers.clip(fn(text)) or "...")


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the text-transform commands."""
    for name, desc, fn in _TRANSFORMS:
        _register(tree, name, desc, fn)
