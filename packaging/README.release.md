# Your all-purpose Discord bot + AI

Welcome! This is your bot. Setup takes about 10 minutes and needs **no coding**.

![Dashboard](docs/screenshots/dashboard.png)

## Quick start

1. Open a terminal in this folder.
2. Run the installer:
   ```
   ./install.sh
   ```
   It installs everything, then asks you a few questions (your Discord token, a
   name for the bot, and an AI key) and saves them for you.
3. Test the AI right in the terminal:
   ```
   make chat
   ```
4. Check everything is working:
   ```
   make doctor
   ```
5. Start the bot:
   ```
   make run
   ```

**Step-by-step beginner guide:** see `docs/GETTING-STARTED.md`
**Getting your Discord token & permissions:** see `docs/DISCORD-SETUP.md`
**What the AI costs:** see `docs/COSTS.md`
**Running 24/7 (host or Docker):** see `docs/DEPLOY.md`
**Opening the dashboard remotely:** see `docs/EXPOSE.md`

## Talking to the bot

Mention the bot in any channel it can see, or set a channel where it chats freely.
It also has slash commands:

`/help` `/ask` `/8ball` `/coinflip` `/dice` `/choose` `/userinfo` `/serverinfo`
`/avatar` `/cat` `/dog`

## Running it 24/7

To keep the bot online on a server, run `uv run mika service install` and follow
the printed instructions.

## License

This is licensed software — see `LICENSE`. Please don't share or redistribute it.
