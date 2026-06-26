# src/mika/ - backend

All Python application code, organized into **three behavior domains** plus shared
foundation and operator layers. Imports point downward only (lower layers never
import higher ones), keeping the code easy to follow and change.

## Behavior domains

| Domain | Package | Audience | Shipped? |
|---|---|---|---|
| **Server** | `bot/` (incl. `bot/features/`) | everyone in a guild (bot account) | yes - the product |
| **AI** | `ai/llm/` + `ai/learning/` | powers the bot; learning is opt-in | yes (learning optional) |

## Shared foundation & operator layers

| Package | Role | May import |
|---|---|---|
| `core/` | config, logging, errors, paths | (nothing internal) |
| `persistence/` | db engine, models, repositories | core |
| `web/` | settings/overview API (no discord) | core, persistence |
| `cli/` | CLI + setup wizard; the entrypoint | everything (orchestrator) |
| `system/` | systemd / process control | core |

Dependency direction: `core <- persistence <- ai <- bot`. The **User** domain lives
in the top-level `userbot/` folder (a standalone selfbot in its own venv, since
`discord.py-self` conflicts with `discord-py`); it is not part of this package and
the bot never imports it. Each package documents itself in its own README.
