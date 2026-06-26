"""`mika invite`: print the correct link to add the bot to a server."""

from __future__ import annotations

import typer
from rich.console import Console

from mika.core.config import get_settings

console = Console()

# view channels + send + read history + embed + attach + add reactions
_PERMISSIONS = 117824


def invite() -> None:
    """Print a server-install invite URL (includes the bot scope)."""
    client_id = get_settings().discord.client_id
    if not client_id or client_id == "CHANGEME":
        console.print("[red]No Application ID set.[/] Run [bold]mika setup[/] and add it.")
        raise typer.Exit(1)
    url = (
        f"https://discord.com/oauth2/authorize?client_id={client_id}"
        f"&permissions={_PERMISSIONS}&scope=bot+applications.commands"
    )
    console.print("Open it, pick [bold]Add to Server[/], and Authorize:\n")
    console.print(url)
    console.print(
        "\n[dim]This is a GUILD install (the `bot` scope) - the bot joins as a member"
        "\nand appears in the server's apps. The Application ID must match your token"
        "\n(check with `mika doctor`).[/]"
    )
