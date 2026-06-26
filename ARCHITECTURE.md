# Architecture

How the codebase fits together, for anyone reading or extending the source.

The backend is organized into **behavior domains** - **server** (`bot/`) and **AI**
(`ai/`) - over a shared foundation and a set of operator surfaces (CLI, web, services).

## Directory tree

```
mika/
├── README.md ARCHITECTURE.md LICENSE       overview + license
├── pyproject.toml .python-version uv.lock  project + toolchain
├── .env.example Makefile install.sh update.sh   config template + entrypoints
│
├── src/mika/                 all Python application code
│   ├── core/                 config · logging · errors · paths        (foundation)
│   ├── persistence/          engine · base · models/ · repositories/  (foundation)
│   │
│   ├── ai/                   ══ AI DOMAIN ══
│   │   ├── llm/              client · providers/ · chat/ · memory/ · tools/   (inference)
│   │   └── learning/         reviewer · feedback · reflection · store  (optional self-learning)
│   │
│   ├── bot/                  ══ SERVER DOMAIN (the Discord bot) ══
│   │   ├── commands/ events/ components/
│   │   └── features/         tickets/ · moderation/
│   │
│   ├── web/                  app · routes/ · templates/   (the control-panel dashboard)
│   ├── cli/                  app · commands/              (the `mika` command)
│   └── system/               systemd / process control
│
└── config/  docs/            persona presets + your config · documentation
```

## The domains

- **Server (`bot/`)** - the Discord bot serving everyone in a guild: slash commands,
  events, components, and `features/` (tickets, moderation).
- **AI (`ai/`)** - the intelligence: `llm/` (inference - providers, chat pipeline,
  memory, tools) and `learning/` (the optional, opt-in self-improvement system).

## Layering (dependencies point downward only)

```
  cli ───────────────┬───────────┐         orchestrates; the entrypoint
   │                 │           │
  bot               web       system        (operator surfaces)
   │                 │           ▼
   ▼                 ▼        systemd
  ai (llm + learning) ──► persistence ──► core
```

Hard boundaries:

- **server (`bot/`) vs AI (`ai/`)** - `ai/llm/` never imports `discord.*`; it serves
  replies, the bot wires them to Discord.
- **inference (`ai/llm/`) vs self-learning (`ai/learning/`)** - learning reviews
  interactions; it does not serve replies.
- **CLI vs web** - separate entrypoints; the CLI may *launch* the web app but shares no
  request code.

Cross-layer needs are met by defining an interface in the lower layer. All config
resolves through `core/config.py` (env / `.env`); all durable state goes through
`persistence/` (SQLite by default, Postgres-ready).

## Runtime surfaces

| Surface | Started by | Lives in |
|---|---|---|
| Bot + dashboard | `mika run` (or the service) | `bot/` + `ai/` + `web/` |
| Control panel | served with the bot, or `mika web` | `web/` |
| Setup wizard | `mika setup` | `cli/` |
| Background service | `mika service ...` | `system/` |
| Self-learning | `mika learning reflect` (+ weekly) | `ai/learning/` (opt-in) |

The dashboard is served in-process by the running bot, so one background service runs
both. A chat turn flows: Discord message → `bot/events` → `ai/llm/client` →
`chat/pipeline` (gather memory + persona + tools) → provider → reply → persist.
