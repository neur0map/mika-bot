"""`mika setup`: one guided flow - bot, AI, web login, memory and personality."""

from __future__ import annotations

import asyncio
import secrets

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from mika.ai.learning.persona_forge import (
    activate,
    all_personas,
    forge_persona,
    persona_summary,
    slugify,
)
from mika.ai.llm.client import LLMClient
from mika.core.config import get_settings
from mika.core.env_file import write_env
from mika.web.auth import hash_password

console = Console()

_INTRO = (
    "Welcome! This sets up your Discord bot + AI in one go - no file editing.\n"
    "When it finishes you'll have a working bot and a web dashboard to run everything.\n\n"
    "Need Discord credentials? Open [bold]docs/DISCORD-SETUP.md[/] in another window."
)
_HONCHO = (
    "[bold]Long-term memory (Honcho)[/] lets the bot remember people and facts across "
    "sessions and recall what's relevant - not just the recent chat.\n"
    "Pros: deeper, personalized replies. Cost: it needs Docker and a little more setup.\n"
    "Skip it and the bot still remembers recent conversation out of the box."
)
_MIN_PASSWORD = 8
_MASK = {"DISCORD_TOKEN", "MIKA_LLM_API_KEY", "MIKA_WEB_PASSWORD"}


def setup() -> None:
    """Run the interactive setup wizard."""
    console.print(Panel(_INTRO, title="mika setup", border_style="red"))
    answers: dict[str, str] = {}

    console.rule("[bold]Discord[/]")
    answers["DISCORD_TOKEN"] = Prompt.ask(
        "[bold]Bot token[/] (Developer Portal -> Bot)", password=True
    )
    answers["DISCORD_CLIENT_ID"] = Prompt.ask(
        "[bold]Application ID[/] (General Information)", default=""
    )

    console.rule("[bold]AI[/]")
    answers["MIKA_PERSONA_NAME"] = Prompt.ask("[bold]Bot display name[/]", default="Mika")
    answers["MIKA_LLM_API_KEY"] = Prompt.ask(
        "[bold]AI key[/] (OpenRouter - openrouter.ai/keys)", password=True
    )
    answers["MIKA_LLM_MODEL"] = Prompt.ask("[bold]Chat model[/]", default="openai/gpt-4o-mini")

    if Confirm.ask("Limit the bot to one server? (recommended)", default=True):
        answers["DISCORD_GUILD_IDS"] = Prompt.ask(
            "  Server ID (right-click server -> Copy ID)", default=""
        )
    if Confirm.ask("Pick a channel where it chats without being @mentioned?", default=False):
        answers["DISCORD_RESPONSE_CHANNEL_IDS"] = Prompt.ask("  Channel ID", default="")

    console.rule("[bold]Web dashboard[/]")
    console.print(
        "[dim]Manage everything from your browser - model, personas, settings. No SSH.[/]"
    )
    answers["MIKA_WEB_EMAIL"] = Prompt.ask("[bold]Dashboard email[/]")
    answers["MIKA_WEB_PASSWORD"] = hash_password(_password())
    answers["MIKA_WEB_SECRET"] = secrets.token_urlsafe(32)

    console.rule("[bold]Memory[/]")
    console.print(Panel(_HONCHO, border_style="grey50"))
    if Confirm.ask("Enable long-term memory (Honcho)?", default=False):
        answers["MIKA_MEMORY_HONCHO_ENABLED"] = "true"
        answers["MIKA_MEMORY_HONCHO_WORKSPACE"] = slugify(answers["MIKA_PERSONA_NAME"])
        answers["MIKA_MEMORY_HONCHO_SESSION"] = "main"
        console.print("  [dim]After setup, run [bold]mika honcho up[/] to start it.[/]")

    console.rule("[bold]Personality[/]")
    choice = _choose_persona()

    _summary(answers)
    if not Confirm.ask("Save and finish?", default=True):
        console.print("[yellow]Cancelled - nothing was written.[/]")
        return
    write_env(answers)
    _apply_persona(choice)
    _done(answers)


def _password() -> str:
    while True:
        password = Prompt.ask("[bold]Dashboard password[/]", password=True)
        if len(password) < _MIN_PASSWORD:
            console.print(f"  [red]Use at least {_MIN_PASSWORD} characters.[/]")
            continue
        if password == Prompt.ask("  Confirm password", password=True):
            return password
        console.print("  [red]Didn't match - try again.[/]")


def _choose_persona() -> tuple[str, str, str]:
    presets = all_personas()
    names = list(presets)
    console.print("Pick a personality (change it or build more anytime in the dashboard):\n")
    for index, name in enumerate(names, 1):
        console.print(f"  [bold]{index}[/]. [bold]{name}[/] - {persona_summary(presets[name])}")
    console.print(
        f"  [bold]{len(names) + 1}[/]. [bold]custom[/] - a famous person or fictional character"
    )
    choices = [str(i) for i in range(1, len(names) + 2)]
    picked = int(Prompt.ask("Choice", choices=choices, default="1"))
    if picked <= len(names):
        return ("preset", names[picked - 1], "")
    character = Prompt.ask("  [bold]Character[/] (e.g. Sherlock Holmes, Tony Stark, Yoda)")
    notes = Prompt.ask("  Notes (optional)", default="")
    return ("custom", character, notes)


def _apply_persona(choice: tuple[str, str, str]) -> None:
    kind, name, notes = choice
    if kind == "preset":
        activate(name)
        console.print(f"  [green]Personality set to {name}.[/]")
        return
    console.print(f"  [dim]Building '{name}' - a few seconds...[/]")
    try:
        path = asyncio.run(forge_persona(LLMClient(), name, notes or name))
        activate(path.stem)
        console.print(f"  [green]Built and set '{path.stem}'.[/]")
    except Exception as error:  # generation hits the network; fall back gracefully
        activate("friendly")
        console.print(
            f"  [yellow]Couldn't build that ({error}); using 'friendly' - retry later.[/]"
        )


def _summary(answers: dict[str, str]) -> None:
    table = Table(title="Review", show_header=True)
    table.add_column("setting")
    table.add_column("value")
    for key, value in answers.items():
        shown = "********" if (key in _MASK and value) else (value or "[dim](blank)[/]")
        table.add_row(key, shown)
    console.print(table)


def _done(answers: dict[str, str]) -> None:
    web = get_settings().web
    steps = (
        f"Dashboard: [bold]http://{web.host}:{web.port}[/]\n"
        f"Log in as: [bold]{answers['MIKA_WEB_EMAIL']}[/]\n\n"
        "Next:\n"
        "  1. [bold]mika doctor[/]              - check everything works\n"
        "  2. [bold]mika service install[/]     - run the bot + dashboard 24/7\n"
        "     (or [bold]mika run[/] to start it in this terminal)"
    )
    console.print(Panel(steps, title="All set", border_style="green"))
