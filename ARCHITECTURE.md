# Architecture

The authoritative map of the repository. Contributor rules are in
[`AGENTS.md`](AGENTS.md); this file explains *how the pieces fit*.

## Directory tree

```
mika-bot/
├── AGENTS.md ARCHITECTURE.md README.md LICENSE      docs + license
├── pyproject.toml .python-version uv.lock           project + toolchain
├── .pre-commit-config.yaml .editorconfig .gitignore guardrails + editor
├── .env.example Makefile install.sh                 config template + entrypoints
│
├── src/mika/                 BACKEND (all Python app code)
│   ├── core/                 config · logging · errors · paths
│   ├── persistence/          engine · base · models/ · repositories/
│   ├── llm/                  client · providers/ · chat/ · memory/ · tools/
│   ├── bot/                  client · commands/ · events/ · components/
│   ├── features/             tickets/ · moderation/ (one folder per feature)
│   ├── web/                  app · routes/ · schemas/   (settings + overview API)
│   ├── cli/                  app · commands/            (the `mika` command)
│   └── system/              manager · units/            (systemd control)
│
├── frontend/                 FRONTEND (templates/ · static/) - separate from backend
├── deploy/                   systemd/ · docker/ (deployment templates)
├── tools/hooks/              dev-only custom git hooks
├── tests/                    mirrors src/mika/
├── docs/                     long-form documentation
└── mikabot(JS)/              GITIGNORED reference material (old JS bot + study repos)
```

Every directory has its own `README.md` describing its purpose and contents.

## Layering (dependencies point downward only)

```
            cli  ─────────────┐  (orchestrates; the entrypoint)
             │                │
   ┌─────────┼─────────┬──────┤
   │         │         │      │
  bot ───► features   web   system
   │  \      │         │      │
   │   \     ▼         ▼      ▼
   └────► llm ──► persistence ──► core
                                   ▲
                    (everything may use core; core uses nothing internal)
```

Hard boundaries that never blur:

- **backend (`src/`) vs frontend (`frontend/`)** - the UI only talks to `web/`'s API.
- **llm (`llm/`) vs bot (`bot/`)** - `llm/` never imports `discord.*` and is usable
  headless; `bot/` calls into `llm/` through its client.
- **cli (`cli/`) vs web (`web/`)** - separate entrypoints; the CLI may *launch* the
  web server but shares no request-handling code with it.
- **service control (`system/`, `deploy/`) vs app logic** - `system/` only renders
  units and drives systemctl.

If a layer needs something from a higher layer, define an interface in the lower
layer and depend on the interface.

## Runtime surfaces

| Surface | Started by | Lives in | Purpose |
|---|---|---|---|
| Discord bot | `mika run` | `bot/` + `llm/` + `features/` | the bot itself |
| Settings/overview web | `mika web` | `web/` + `frontend/` | localhost config + dashboard |
| Setup wizard | `mika setup` | `cli/` | first-run configuration |
| Services | `mika service ...` | `system/` + `deploy/` | systemd install/start/stop |

## Data flow (a chat turn, once implemented)

```
Discord message ──► bot/events/message ──► llm/client ──► llm/chat/pipeline
   gather context (llm/memory + persistence) ──► llm/chat/prompt ──► provider
   ──► reply ──► bot sends ──► persist turn (persistence)
```

## Configuration & storage

- All config resolves through `core/config.py` (env / `.env`), never scattered
  `os.getenv`.
- All durable state goes through `persistence/` (sqlite by default, postgres-ready);
  no other layer issues queries.
