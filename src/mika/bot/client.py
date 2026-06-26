"""Discord client bootstrap: intents, command registration, event wiring."""

from __future__ import annotations

import discord
from discord.ext import commands

from mika.ai.llm.client import LLMClient
from mika.bot.commands import register_all
from mika.bot.events import register_events
from mika.bot.scheduler import start_schedulers
from mika.core.config import get_settings
from mika.core.logging import configure_logging, get_logger
from mika.persistence.engine import init_db

logger = get_logger(__name__)


class BotApp(commands.Bot):
    """The bot application: a Discord client plus the LLM brain."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="\u200b", intents=intents, help_command=None)
        self.llm = LLMClient()

    async def setup_hook(self) -> None:
        await init_db()
        await self.llm.startup()
        start_schedulers(self)
        register_all(self.tree)
        guild_ids = get_settings().discord.guild_id_list
        if not guild_ids:
            await self.tree.sync()
            logger.info("commands synced (global)")
            return
        for gid in guild_ids:
            guild = discord.Object(id=int(gid))
            self.tree.copy_global_to(guild=guild)
            try:
                await self.tree.sync(guild=guild)
                logger.info("commands synced (guild %s)", gid)
            except discord.HTTPException as error:
                logger.warning(
                    "couldn't sync commands to guild %s (%s); is the bot invited "
                    "there? run 'mika invite'. staying online - commands sync once it joins.",
                    gid,
                    error,
                )


def run() -> None:
    """Start the bot. Entry point for `mika run`."""
    settings = get_settings()
    configure_logging(settings.log_level)
    token = settings.discord.token
    if not token or token == "CHANGEME":  # noqa: S105
        raise SystemExit("DISCORD_TOKEN is not set. Run `mika setup` first.")
    bot = BotApp()
    register_events(bot)
    try:
        bot.run(token, log_handler=None)
    except discord.PrivilegedIntentsRequired as error:
        raise SystemExit(
            "Discord rejected the bot: a required intent is OFF.\n"
            "Fix: Developer Portal -> your app -> Bot -> Privileged Gateway Intents ->\n"
            "turn ON 'MESSAGE CONTENT INTENT', save, then run `mika run` again."
        ) from error
    except discord.LoginFailure as error:
        raise SystemExit("Discord rejected the token. Re-check it with `mika setup`.") from error
