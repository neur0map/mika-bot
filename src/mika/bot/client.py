"""Discord client bootstrap: intents, command registration, event wiring."""

from __future__ import annotations

import asyncio
import contextlib

import discord
import uvicorn
from discord.ext import commands

from mika.ai.llm.client import LLMClient
from mika.ai.llm.social_policy import SocialActionPolicy
from mika.bot.events import register_events
from mika.bot.scheduler import start_schedulers
from mika.core.config import get_settings
from mika.core.logging import configure_logging, get_logger
from mika.persistence.engine import init_db
from mika.web.app import create_app

logger = get_logger(__name__)


class _QuietServer(uvicorn.Server):
    """A uvicorn server that lets the bot process own the shutdown signals."""

    def install_signal_handlers(self) -> None:
        return None


class BotApp(commands.Bot):
    """The bot application: a Discord client plus the LLM brain."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="\u200b", intents=intents, help_command=None)
        self.llm = LLMClient()
        self.social_policy = SocialActionPolicy()
        self._web_task: asyncio.Task[None] | None = None

    async def setup_hook(self) -> None:
        await init_db()
        await self.llm.startup()
        start_schedulers(self)
        self._start_web()

    def _start_web(self) -> None:
        """Serve the dashboard in the background so one service runs the bot + panel."""
        web = get_settings().web
        if not web.enabled:
            return
        config = uvicorn.Config(create_app(), host=web.host, port=web.port, log_level="warning")
        server = _QuietServer(config)
        self._web_task = asyncio.create_task(self._serve_web(server), name="dashboard")
        logger.info("dashboard on http://%s:%s", web.host, web.port)

    async def _serve_web(self, server: _QuietServer) -> None:
        try:
            await server.serve()
        except (SystemExit, OSError) as error:
            # port already in use, etc. - uvicorn calls sys.exit(1); keep the bot alive
            logger.warning(
                "dashboard could not start on port %s (%s); bot continues without it",
                get_settings().web.port,
                error,
            )
        except Exception as error:
            logger.warning("dashboard did not start (bot keeps running): %s", error)

    async def close(self) -> None:
        if self._web_task is not None:
            self._web_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._web_task
        await super().close()


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
