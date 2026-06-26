# Roadmap & feature backlog

Future work for the bot, captured from the owner. **Nothing here is built yet** — this
is an unordered backlog (not a commitment or a sequence). Some items extend things that
already exist; those are flagged inline as _today: …_.

> `dev_docs/` is internal planning and is **not** shipped in the customer release zip
> (the packager ships only `src/`, `config/`, `docs/`, the installer, and user docs).

---

## Guiding principles

- [ ] **Slash vs AI cost clarity.** Make it explicit everywhere: the bot is fully usable on **slash commands alone** (free); **every AI feature runs through OpenRouter** and costs money. Surface this in the docs, the wizard, and the dashboard.
- [ ] **Dashboard-first setup.** Most complex features should be configured **only via the dashboard** — they get too fiddly for the wizard / `.env`.
- [ ] **Parallel task processing.** Run independent jobs (reflection, media fetch, OSINT lookups, etc.) as parallel background tasks rather than blocking.

## Documentation

- [ ] Simplify the docs **a lot** more — shorter, friendlier, less jargon.
- [ ] Add **screenshots** throughout (setup wizard, dashboard, Discord results).
- [ ] Document how **persona creation** works, with an **estimated cost per personality** (CrewSoul model usage).
- [ ] Clearly explain the **slash-commands-are-standalone / all-AI-runs-on-OpenRouter** cost split (see principles).

## Installer & deployment

- [ ] Installer **auto-detects and installs all prerequisites** if they aren't present (not just `uv` — everything the bot needs).
- [ ] **Dockerfile + deploy script.** Offer a clean choice at install time: **install on the host** _or_ **run in a Docker container**.
- [ ] **Auto server starter templates / cloner** — spin up a ready-made Discord server layout (channels, roles, categories) from a template.
- [ ] Document exposing the dashboard remotely:
  - [ ] **Cloudflare Tunnel**
  - [ ] **Tailscale** (and/or plain port forwarding)

## AI personas & CrewSoul

- [ ] Ship **several preset personalities** to pick from out of the box.
- [ ] **Update / switch persona without losing data** — safe editing that preserves memory and settings.
- [ ] Improve the **starting persona, skills, and rules** (better defaults).
- [ ] **Full CrewSoul integration** (_today: exists as a separate reference tool_):
  - [ ] Run CrewSoul from the **terminal wizard** too (not only the dashboard).
  - [ ] Use the user's **OpenRouter key**; **we preset** the smartest, price-balanced models for **personality creation**.
  - [ ] User only picks their **main training model**; everything else is preset for them.
  - [ ] Docs on **how it works** + **estimated cost per personality**.
- [ ] **Weekly self-reflection** process for the AI (_today: learning subsystem is scaffolded but not wired_).

## Dashboard (web UI)

- [ ] Build a **beautiful, eye-candy dashboard** (_today: minimal read-only overview page via `mika web`_).
- [ ] Make it the **primary setup surface** for complex features (per principles).
- [ ] Remote-access instructions (Cloudflare Tunnel / Tailscale — see deployment).

## Commands & organization

- [ ] Keep **adding commands** to test, and **organize them properly** in the directory (clear per-category layout, stay under Discord's 100-command cap).

## Moderation & community

- [ ] **Welcome new users** + a **moderator role** / feature set.
- [ ] Port common **moderator-bot features**: **giveaways**, **auto-moderation / chat moderation**, etc.
- [ ] **Ticketing system** setup.
- [ ] **Clone emojis** from other servers.

## Media & entertainment

- [ ] **Klipy** (GIFs): setup **docs + wizard step** (_today: `MIKA_KLIPY_*` env vars exist but aren't wired into chat_).
- [ ] **Music** (always-on):
  - [ ] Auto-create **music channels**.
  - [ ] **Spotify** (or other) music setup.
  - [ ] _Or_ **download music videos and just play them**.
  - [ ] A **request channel** where users pick the song to play.
  - [ ] Backend: **cobalt.tools** — user pastes a URL, the song is added to the queue.
  - [ ] **Guardrails**: max video/track length, queue limits, etc.
- [ ] **Anime tools** — for both the AI and slash commands.
- [ ] **Image generation.**
- [ ] **TTS** (text-to-speech).
- [ ] **Voice calls** — _future; can be expensive_.
- [ ] **Custom RPC** (Rich Presence).

## Security / OSINT (green-area only)

- [ ] **Sherlock** integration — username search via a tool / slash command.
- [ ] **Enumeration** slash commands for light, lawful info-gathering.
- [ ] General **OSINT tools** — green-area / educational use only.
