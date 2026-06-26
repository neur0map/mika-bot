"""`mika setup`: the friendly first-run wizard that writes your .env."""

from __future__ import annotations

import re
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()

_INTRO = (
    "Welcome! I'll set up your all-purpose Discord bot + AI.\n"
    "I'll ask a few questions and save everything for you - no file editing.\n\n"
    "Need credentials? Open [bold]docs/DISCORD-SETUP.md[/] in another window."
)


def setup() -> None:
    """Run the interactive setup wizard."""
    console.print(Panel(_INTRO, title="Mika setup", border_style="cyan"))

    answers: dict[str, str] = {}
    answers["DISCORD_TOKEN"] = Prompt.ask(
        "[bold]Discord bot token[/] (from the Bot tab)", password=True
    )
    answers["DISCORD_CLIENT_ID"] = Prompt.ask(
        "[bold]Application ID[/] (General Information tab)", default=""
    )
    answers["MIKA_PERSONA_NAME"] = Prompt.ask("[bold]Bot display name[/]", default="Mika")
    answers["MIKA_LLM_API_KEY"] = Prompt.ask(
        "[bold]AI key[/] (OpenRouter - openrouter.ai/keys)", password=True
    )
    answers["MIKA_LLM_MODEL"] = Prompt.ask("[bold]AI model[/]", default="openai/gpt-4o-mini")

    if Confirm.ask("Limit the bot to one server? (recommended for testing)", default=True):
        answers["DISCORD_GUILD_IDS"] = Prompt.ask(
            "  Server ID (right-click server -> Copy Server ID)", default=""
        )
    if Confirm.ask("Pick one channel where the bot chats without being @mentioned?", default=False):
        answers["DISCORD_RESPONSE_CHANNEL_IDS"] = Prompt.ask("  Channel ID", default="")

    _summary(answers)
    if not Confirm.ask("Save this to .env?", default=True):
        console.print("[yellow]Cancelled - nothing was written.[/]")
        return
    _write_env(answers)
    _done()


def _summary(answers: dict[str, str]) -> None:
    table = Table(title="Review", show_header=True)
    table.add_column("setting")
    table.add_column("value")
    masked = {"DISCORD_TOKEN", "MIKA_LLM_API_KEY"}
    for key, value in answers.items():
        shown = "••••••••" if (key in masked and value) else (value or "[dim](blank)[/]")
        table.add_row(key, shown)
    console.print(table)


def _write_env(answers: dict[str, str]) -> None:
    example = Path(".env.example")
    lines = example.read_text(encoding="utf-8").splitlines() if example.exists() else []
    written: set[str] = set()
    out: list[str] = []
    for line in lines:
        match = re.match(r"^([A-Z][A-Z0-9_]+)=", line)
        if match and match.group(1) in answers:
            out.append(f"{match.group(1)}={answers[match.group(1)]}")
            written.add(match.group(1))
        else:
            out.append(line)
    out.extend(f"{key}={value}" for key, value in answers.items() if key not in written)
    Path(".env").write_text("\n".join(out) + "\n", encoding="utf-8")


def _done() -> None:
    steps = (
        "Saved to [bold].env[/]\n\n"
        "Next:\n"
        "  1. [bold]mika doctor[/]   - check everything works\n"
        '  2. [bold]mika chat "hi"[/]  - test the AI in the terminal\n'
        "  3. [bold]mika run[/]      - start the bot in Discord"
    )
    console.print(Panel(steps, title="All set", border_style="green"))
