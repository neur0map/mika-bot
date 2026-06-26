# Deploying the bot

Two ways to keep the bot running 24/7. Pick whichever you're comfortable with -
both work on a laptop, a Raspberry Pi, or a cheap VPS.

## Option A - On the host (no Docker)

The simplest path. The installer already set up the `mika` command.

```bash
mika service install   # runs the bot 24/7, survives reboots
mika service status    # check it's running
mika logs -f           # watch live logs
mika service stop      # stop it
```

On a server you're logged into as root, this installs a system service. On your own
laptop it installs a personal one (no admin password needed). That's the whole story.

The **dashboard runs with the bot** - once the service is up, the panel is live at
`http://127.0.0.1:8080` (no separate process, terminal stays free). `mika web` is only
for viewing the panel on its own. See [EXPOSE.md](EXPOSE.md) to reach it remotely.

## Option B - In a container (Docker)

Good if you already use Docker or want the bot isolated from the rest of the system.

```bash
mika setup             # create your .env (token, AI key, persona) - one time
docker compose up -d   # build and run the bot in the background
docker compose logs -f # watch logs
docker compose down    # stop it
```

Your `.env` holds the configuration and `./var` holds conversation memory + logs, both
mounted into the container so nothing is lost when you rebuild or restart.

## Which should I choose?

| | Host (Option A) | Docker (Option B) |
|---|---|---|
| Setup | `mika service install` | `docker compose up -d` |
| Isolation | shares the system | fully isolated |
| Needs Docker | no | yes |
| Best for | most people, VPS | Docker users, multi-app servers |

**Recommendation:** if you're not sure, use **Option A** - it's one command and needs
nothing extra. Use Docker only if you already have it and prefer containers.

## Long-term memory (optional)

Either option can add Honcho for semantic long-term memory. See
[HONCHO-MEMORY.md](HONCHO-MEMORY.md). It needs Docker and is entirely optional - the
bot remembers recent conversation out of the box without it.
