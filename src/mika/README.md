# src/mika/ - backend

All Python application code. No frontend assets, no dev tooling. The package is
layered and imports only point downward (full rules in ../../AGENTS.md section 3).

| Package | Role | May import |
|---|---|---|
| `core/` | config, logging, errors, paths | (nothing internal) |
| `persistence/` | db engine, models, repositories | core |
| `llm/` | providers, chat, memory, tools (no discord) | core, persistence |
| `bot/` | discord client, commands, events | core, llm, features, persistence |
| `features/` | pluggable feature modules | core (+ interfaces) |
| `web/` | settings/overview API (no discord) | core, persistence |
| `cli/` | CLI + setup wizard; the entrypoint | core, system, web, bot |
| `system/` | systemd / process control | core |

One concern per file, files under 500 lines, full type hints. Each package
documents itself in its own README.
