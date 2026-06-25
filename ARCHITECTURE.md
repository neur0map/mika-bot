# Architecture

The authoritative map of the repository. Contributor rules are in
[`AGENTS.md`](AGENTS.md); this file explains *how the pieces fit*.

The backend is organized into **three behavior domains** - **server** (`bot/`),
**user** (`userbot/`), and **AI** (`ai/`) - over a shared foundation and operator
layers.

## Directory tree

```
mika-bot/
├── AGENTS.md ARCHITECTURE.md README.md LICENSE      docs + license
├── pyproject.toml .python-version uv.lock           project + toolchain
├── .pre-commit-config.yaml .editorconfig .gitignore guardrails + editor
├── .env.example Makefile install.sh                 config template + entrypoints
│
├── src/mika/                 BACKEND (all Python app code)
│   ├── core/                 config · logging · errors · paths        (foundation)
│   ├── persistence/          engine · base · models/ · repositories/  (foundation)
│   │
│   ├── ai/                   ══ AI DOMAIN ══
│   │   ├── llm/              client · providers/ · chat/ · memory/ · tools/      (inference)
│   │   └── learning/         reviewer/(agent·skills·tools·rules) · feedback/ ·
│   │                         reflection/ · store          (OPTIONAL self-learning)
│   │
│   ├── bot/                  ══ SERVER DOMAIN (bot account; compliant; shipped) ══
│   │   ├── commands/ events/ components/
│   │   └── features/         tickets/ · moderation/
│   │
│   ├── userbot/              ══ USER DOMAIN (selfbot; personal; ToS-grey; NOT shipped) ══
│   │   └── commands/         (non-destructive only)
│   │
│   ├── web/                  app · routes/ · schemas/     (settings + overview API)
│   ├── cli/                  app · commands/              (the `mika` command)
│   └── system/               manager · units/             (systemd control)
│
├── frontend/                 FRONTEND (templates/ · static/) - separate from backend
├── deploy/                   systemd/ · docker/ (deployment templates)
├── tools/hooks/              dev-only custom git hooks
├── tests/  docs/             tests mirror src/mika/ · documentation
└── mikabot(JS)/              GITIGNORED reference material (old JS bot + study repos)
```

Every directory has its own `README.md` describing its purpose and contents.

## The three domains

- **Server (`bot/`)** - a Discord *bot account* serving everyone in a guild. The
  compliant, sellable core. Slash commands, events, components, and `features/`.
- **User (`userbot/`)** - automation on the *owner's own account* (a selfbot) for
  personal QoL. ToS-grey, non-destructive, **never distributed**, and run as a
  **separate process** (its `discord.py-self` cannot share an env with `discord-py`).
- **AI (`ai/`)** - shared intelligence: `llm/` (inference) and `learning/` (the
  optional, opt-in self-learning system that reviews interactions with the external
  Hermes agent). Used by the server bot and, if desired, the userbot.

## Layering (dependencies point downward only)

```
  cli ─────────────────────────────────────────┐   orchestrates; the entrypoint
   │                                            │
   ├──────────┬──────────┬──────────┬───────────┤
  bot      userbot       web       system   (operator surfaces)
   │  \       │ (separate  │         │
   │   \      │  runtime)  │         ▼
   ▼    ▼     ▼            ▼      systemd
  ai (llm + learning) ──► persistence ──► core
                                            ▲
              (everything may use core; core imports nothing internal)
```

Hard boundaries that never blur:

- **server (`bot/`) vs user (`userbot/`) vs AI (`ai/`)** - the three domains.
- **backend (`src/`) vs frontend (`frontend/`)** - the UI only talks to `web/`'s API.
- **inference (`ai/llm/`) vs self-learning (`ai/learning/`)** - learning reviews,
  it does not serve replies; `llm/` never imports `discord.*`.
- **cli vs web** - separate entrypoints; the CLI may *launch* web but shares no
  request code.
- **shipped product (everything except `userbot/`) vs personal (`userbot/`)** - the
  bot never imports `userbot/`.

Cross-layer needs are met by defining an interface in the lower layer.

## Runtime surfaces

| Surface | Started by | Lives in | Ships? |
|---|---|---|---|
| Server bot | `mika run` | `bot/` + `ai/` + `features/` | yes |
| Settings/overview web | `mika web` | `web/` + `frontend/` | yes |
| Setup wizard | `mika setup` | `cli/` | yes |
| Services | `mika service ...` | `system/` + `deploy/` | yes |
| Self-learning reflection | `mika learning reflect` (+ timer) | `ai/learning/` | yes (opt-in) |
| User companion | `mika userbot run` | `userbot/` (separate venv) | **no - personal** |

## Data flow

A chat turn (server domain):

```
Discord message ──► bot/events/message ──► ai/llm/client ──► ai/llm/chat/pipeline
   gather context (ai/llm/memory + persistence + lessons) ──► chat/prompt ──► provider
   ──► reply ──► bot sends ──► persist turn (persistence)
```

The self-learning loop (AI domain, optional, async):

```
interactions ──► ai/learning/feedback ──► reviewer (Hermes agent) applies rules
   ──► distilled lessons ──► ai/learning/store ──► back into chat/prompt
```

## Configuration & storage

- All config resolves through `core/config.py` (env / `.env`); never scattered
  `os.getenv`.
- All durable state goes through `persistence/` (sqlite by default, postgres-ready);
  no other layer issues queries.
