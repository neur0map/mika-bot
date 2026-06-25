# userbot/ - USER-ACCOUNT domain (personal, ToS grey area, NOT shipped)

Quality-of-life automation that runs on **your own Discord account** (a selfbot),
for things a bot account cannot do. Kept strictly separate from the compliant
server bot.

> WARNING - read before touching:
> - Automating a user account violates Discord's ToS and risks an account ban.
>   Keep it **non-destructive and personal**; never resell or distribute it.
> - It is **excluded from the customer distribution.** The sellable product is the
>   compliant bot only (`bot/` + `ai/` + foundation); release builds drop `userbot/`.
> - It needs a **separate runtime**: a USER token and `discord.py-self`, which ships
>   the same `discord` module as `discord-py` and therefore **cannot share a
>   virtualenv/process** with the bot. Run it in its own environment.
> - `userbot/` may use `core/` and `ai/llm/`; the bot must **never** import
>   `userbot/`, and `userbot/` must never perform destructive actions.

- `client.py` - selfbot client bootstrap (separate user token).
- `commands/` - user-account QoL commands, one file each (non-destructive only).

Install its dependency (`discord.py-self`) in a **separate** venv; do not add it to
the project's main `pyproject.toml` (it conflicts with `discord-py`).
