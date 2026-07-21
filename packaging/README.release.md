# Your Discord conversation companion

Welcome! This is your bot. Setup takes about 10 minutes and needs **no coding**.

![Dashboard](docs/screenshots/dashboard.png)

## Quick start

1. Open a terminal in this folder.
2. Run the installer:
   ```
   ./install.sh
   ```
   It installs everything, then asks a few questions - your Discord token, an AI key,
   and an email + password for your **web dashboard** - and offers to start the bot
   right away.
3. Open your dashboard at the address it prints (usually `http://127.0.0.1:8080`) and
   log in. Change the model and edit settings with no coding or SSH.

![Control panel](docs/screenshots/web-settings.png)

Prefer the terminal? `make chat` tests the AI, `make doctor` checks everything, and
`make run` starts the bot in the foreground.

**Guides:**
- `docs/GETTING-STARTED.md` - step-by-step beginner walkthrough
- `docs/DASHBOARD.md` - the web control panel
- `docs/DISCORD-SETUP.md` - your Discord token & permissions
- `docs/COSTS.md` - what the AI costs
- `docs/DEPLOY.md` - running 24/7 (host or Docker)
- `docs/EXPOSE.md` - opening the dashboard to your phone safely

## Talking to the bot

Mention the bot in an allowed channel, or set a dedicated channel where it chats freely.
It responds concisely and may react or use optional media when socially appropriate.

## Running it 24/7

The installer offers to do this for you. Anytime, run `mika service install` to keep the
bot **and** its dashboard running in the background (survives reboots).

## License

This is licensed software — see `LICENSE`. Please don't share or redistribute it.
