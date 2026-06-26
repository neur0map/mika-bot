# userbot/ — personal user-account companion (NOT sold, NOT supported)

Standalone selfbot for your **own** Discord account — quality-of-life only.

> **Read before using.** Automating a user account violates Discord's Terms of
> Service and can get your account **banned**. This is personal, non-destructive,
> opt-in tooling. It is **excluded from the release zip** and is never part of the
> product sold to customers. The bot never imports this; it runs entirely on its own.

It uses `discord.py-self`, which ships the same `discord` module as the bot's
`discord.py` and **cannot share the bot's virtualenv**. So it lives here as a
separate mini-project with its own environment.

## Run it (separate from the bot)

```bash
cd userbot
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export USERBOT_TOKEN="your-user-token"   # keep secret; never share
python main.py
```

## Commands

Prefix defaults to `.` (set `USERBOT_PREFIX` to change):

- `.ping` — show latency (edits your own message)
- `.afk <message>` — auto-reply when you're mentioned; send any message to clear behavior next run

Keep additions **non-destructive** — no mass actions, scraping, or spam.
