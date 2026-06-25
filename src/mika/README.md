# src/mika/ - backend

All Python application code, organized into **three behavior domains** plus shared
foundation and operator layers. Imports point downward only (../../AGENTS.md s3).

## Behavior domains

| Domain | Package | Audience | Shipped? |
|---|---|---|---|
| **Server** | `bot/` (incl. `bot/features/`) | everyone in a guild (bot account) | yes - the product |
| **User** | `userbot/` | the owner's own account (selfbot) | NO - personal, ToS-grey |
| **AI** | `ai/llm/` + `ai/learning/` | powers both; learning is opt-in | yes (learning optional) |

## Shared foundation & operator layers

| Package | Role | May import |
|---|---|---|
| `core/` | config, logging, errors, paths | (nothing internal) |
| `persistence/` | db engine, models, repositories | core |
| `web/` | settings/overview API (no discord) | core, persistence |
| `cli/` | CLI + setup wizard; the entrypoint | everything (orchestrator) |
| `system/` | systemd / process control | core |

Dependency direction: `core <- persistence <- ai <- bot`. `userbot` depends only on
`core` + `ai/llm` and runs as a **separate process/venv** (its `discord.py-self`
conflicts with `discord-py`). The bot must **never** import `userbot/`. Each package
documents itself in its own README.
