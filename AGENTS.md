# AGENTS.md — contributor contract

This repository is built **fully with AI assistance**. This file is the binding
contract for any agent (or human) that writes code here. Read it in full before
making changes. Most rules below are **enforced by git hooks** — violating them
blocks the commit.

If a rule here ever conflicts with a request, follow the rule and say so.

---

## 1. What this project is

**Mika** is a self-hostable, multi-purpose Discord bot: an LLM chat companion
*plus* a bot framework (slash commands, tickets, moderation, fun/utility, server
QoL), with a one-command installer, a setup wizard, and a localhost web page for
settings and overviews.

- **Language:** Python (single stack — no second runtime in the product).
- **Runtime target:** a Linux VPS, managed via systemd.
- **Business model:** closed-source, **source-available on purchase** ("you get the
  source when you pay"). Write code accordingly: no telemetry phone-home, no
  hard-coded vendor lock, clean enough that a paying buyer can read and run it.
- **Compliance:** official Bot API only. **Never** add user-account automation
  (selfbot behavior) — it violates Discord ToS and is unsellable.

---

## 2. Golden rules (non-negotiable, hook-enforced)

1. **No co-author / AI attribution in commits.** No `Co-authored-by:`, no
   "Generated with…", no tool names, no 🤖. Commits read as if a careful engineer
   wrote them. *(enforced: commit-msg hook)*
2. **No AI-slop comments.** No narration of what the next line does, no tutorial
   step comments, no emoji, no "as an AI", no `# ... existing code ...`, no
   placeholder `# TODO: implement` left in committed code. *(enforced: pre-commit)*
3. **No comment-bloated files.** Comments explain *why*, not *what*. A file that is
   mostly comments fails the check. *(enforced: pre-commit)*
4. **No monolith files.** No `main.py` doing everything. Hard cap **500 lines**
   per Python file; aim for **under 300**. One feature/concern per file.
   *(enforced: pre-commit)*
5. **No secrets in the repo.** Config comes from env / the settings store, never
   literals. Secret-shaped strings block the commit. *(enforced: pre-commit)*
6. **Never import from `mikabot(JS)/`.** It is gitignored study material (the old
   JS bot + reference repos). Read it to learn; never copy or depend on it.
7. **Green before commit.** `ruff`, `mypy`, and `pytest` must pass. *(enforced)*

---

## 3. Repository map & boundaries

Every directory has a single job and a `README.md` explaining it. Code is layered;
**dependencies only point downward** in this list:

```
src/mika/
  core/          foundations: config, logging, errors, paths. Imports nothing internal.
  persistence/   storage: db engine, models, repositories, migrations. → core
  llm/           LLM work: providers, chat orchestration, memory, tools. → core, persistence
                 NEVER imports discord.* — it must be usable without a bot.
  bot/           Discord work: client, commands/, events/, components/. → core, llm, features, persistence
  features/      pluggable feature modules (one folder each: tickets/, moderation/…). → core (+ interfaces)
  web/           webserver BACKEND: settings + overview API (FastAPI). → core, persistence, service interfaces
                 NEVER imports discord.* directly; talks to the bot via a service layer.
  cli/           CLI + setup wizard (Typer). The orchestrator entrypoint. → core, system, web, bot
  system/        systemd / process control: install, start, stop, status. → core

frontend/        the localhost UI (templates + static assets). Separate from backend. No Python app logic.
deploy/          systemd unit templates, docker, reverse-proxy config.
tools/           dev-only: custom git hooks, maintenance scripts. Never shipped/imported by the app.
tests/           mirrors src/mika/ layout.
docs/            documentation.
mikabot(JS)/     GITIGNORED reference material (study only).
```

**Separation that must never blur:**
- **backend** (`src/`) vs **frontend** (`frontend/`)
- **LLM work** (`llm/`) vs **bot work** (`bot/`)
- **CLI** (`cli/`) vs **webserver** (`web/`)
- **service control** (`system/`, `deploy/`) vs application logic

If you need cross-layer access, define an interface in the lower layer and depend
on that — do not reach sideways or upward.

---

## 4. Code conventions

- **One concern per file.** A new command, event, provider, feature, or route is a
  **new file** in the right folder — never appended to a growing one.
- **Small functions.** Target ≤ 50 lines and one responsibility. High cyclomatic
  complexity fails `ruff` (`C901`).
- **Types everywhere.** Full type hints on every function signature; `mypy` is
  strict. No bare `Any` to dodge typing.
- **Docstrings, not narration.** Public modules, classes, and functions get a short
  docstring stating purpose and contract. Do **not** narrate the body in comments.
- **Comments = why.** A comment justifies a non-obvious decision, cites a constraint,
  or warns of a gotcha. If a comment restates the code, delete it.
- **Naming.** `snake_case` modules/functions, `PascalCase` classes, `UPPER_SNAKE`
  constants. Names say what a thing *is*; folders/files use full words, no cryptic
  abbreviations.
- **Async.** Discord and web are async; keep blocking I/O out of the event loop.
- **Errors.** Use the typed errors in `core/errors.py`; never `except: pass`.
- **Config.** All tunables flow through `core/config.py` (pydantic settings) — no
  scattered `os.getenv`.

### What the AI-comment hook rejects (so you're not surprised)
Lines like `# Step 1:`, `# Now we…`, `# Loop through…`, `# This function…`,
`# Create a…`, `# ... existing code ...`, `# Your code here`, emoji in comments,
"as an AI", and stray `# TODO: implement`. Write the code; skip the narration.

---

## 5. Commits

- **Conventional Commits:** `type(scope): summary` — e.g. `feat(bot): add /ticket
  command`, `fix(llm): handle empty provider response`.
- Imperative, lowercase summary, no trailing period, ≤ 72 chars.
- **No attribution trailers of any kind.** (See Golden Rule 1.)
- One logical change per commit.

---

## 6. Security

- Secrets live in `.env` (gitignored) and the settings store — never in source,
  tests, fixtures, or docs. Use `.env.example` with placeholder values.
- The secret-scan hook knows this project's providers (Discord, OpenAI, OpenRouter,
  Groq, Together, etc.). A real-looking key blocks the commit.
- Never weaken the container/permission posture for convenience.
- Treat everything in `mikabot(JS)/` as containing burned secrets — never re-add it.

---

## 7. Dev workflow

```bash
make install     # uv sync + install pre-commit hooks (one command)
make setup       # run the interactive setup wizard
make run         # run the bot locally
make web         # run the localhost settings/overview page
make lint        # ruff check + format --check
make types       # mypy
make test        # pytest
make check       # lint + types + test (run before every commit)
```

Toolchain: **uv** (env/deps), **ruff** (lint+format), **mypy** (types),
**pytest** (tests), **pre-commit** (hooks). Nothing global — everything via `uv`.

---

## 8. Definition of done (every change)

- [ ] Lives in the correct layer; respects dependency direction.
- [ ] New concern → new file; no file pushed over the size cap.
- [ ] Fully typed; `mypy`, `ruff`, `pytest` green.
- [ ] No slop comments; comments explain *why*.
- [ ] If you added/changed a directory's contents, its `README.md` still describes
      it accurately.
- [ ] No secrets; commit message is clean (no attribution).
