#!/usr/bin/env bash
# One-command installer for the bot (for end users).
# Installs the uv toolchain if missing, installs the bot's dependencies, ensures a
# .env exists, then launches the friendly setup wizard. No developer tooling.
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

if ! command -v uv >/dev/null 2>&1; then
    say "Installing uv (the Python toolchain)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

say "Installing the bot (this also sets up Python automatically)..."
uv sync --no-dev

[ -f .env ] || cp .env.example .env

say "Starting the setup wizard..."
uv run mika setup

echo
say "Done! Test it with:  make chat   (or: uv run mika chat \"hello\")"
say "Then start it with:  make run    (or: uv run mika run)"
