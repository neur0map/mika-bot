# The web control panel

Run and manage the whole bot from your browser - no SSH, no editing files. The
dashboard runs **with the bot** (one service), at `http://127.0.0.1:8080` by default.

## Logging in

The dashboard is gated by a single owner account (email + password). You set it during
`mika setup`. If you ever skipped that, the first time you open the dashboard it asks you
to create the account right there. Reset it anytime by re-running `mika setup`.

Passwords are hashed (PBKDF2) and stored locally in `.env`; nothing leaves your server.

## What you can do

- **Overview** - conversation mode, active persona, selected model, memory, and media
  availability at a glance.
- **Settings** - edit everything: chat model, AI key, creativity, reply length, web
  search, short- and long-term memory, the Discord token/IDs, and the GIF key. Secrets
  show as "set - leave blank to keep" so they never display. Fields tagged **restart**
  (token, AI key, memory) take effect after the bot restarts - there's a button for it.
- **Personas** - switch personality instantly (memory is kept), or **build a new one**:
  type any famous person or fictional character and the bot generates a persona that
  captures their voice. Switching is live; building takes a few seconds.

## Opening it remotely

It binds to localhost. To reach it from your phone or another machine, use Tailscale or
a Cloudflare Tunnel - see [EXPOSE.md](EXPOSE.md). The panel is read/write, so keep the
link private (Tailscale is the safest option).

## Running it

It comes up automatically with the bot:

```bash
mika service install   # bot + dashboard, 24/7, survives reboots
mika service status
```

To view the panel without the bot (e.g. for a quick look), `mika web` serves it alone.
