#!/usr/bin/env python3
"""Personal user-account companion (selfbot) - RUN IN ITS OWN VIRTUALENV.

WARNING: automating a Discord user account violates Discord's Terms of Service and
can get the account banned. This is for personal, non-destructive use only and is
NOT part of the product sold to customers (the release zip excludes this folder).

It needs `discord.py-self`, which provides the same `discord` module as the bot's
`discord.py` and therefore cannot share the bot's virtualenv. Run it separately:

    cd userbot
    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    export USERBOT_TOKEN="your-user-token"   # keep this secret; never share it
    python main.py

Commands (prefix defaults to "."): ".ping", ".afk <message>".
"""

from __future__ import annotations

import os

import discord
from discord.ext import commands

PREFIX = os.environ.get("USERBOT_PREFIX", ".")
TOKEN = os.environ.get("USERBOT_TOKEN", "")

bot = commands.Bot(command_prefix=PREFIX, help_command=None)
_afk: dict[str, str] = {}


@bot.event
async def on_ready() -> None:
    print(f"userbot ready as {bot.user}")


@bot.command()
async def ping(ctx: commands.Context) -> None:
    """Reply with latency by editing your own command message."""
    await ctx.message.edit(content=f"pong ({round(bot.latency * 1000)}ms)")


@bot.command()
async def afk(ctx: commands.Context, *, message: str = "AFK") -> None:
    """Set an auto-reply for when you are mentioned."""
    _afk["message"] = message
    await ctx.message.edit(content=f"afk set: {message}")


@bot.event
async def on_message(message: discord.Message) -> None:
    await bot.process_commands(message)
    if not _afk or bot.user is None:
        return
    if bot.user in message.mentions and message.author.id != bot.user.id:
        await message.channel.send(_afk["message"])


def main() -> None:
    if not TOKEN:
        raise SystemExit("Set USERBOT_TOKEN (your Discord USER token) first.")
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
