#!/usr/bin/env bash
# One-command installer for Mika.
# Installs the uv toolchain if missing, syncs dependencies, wires git hooks
# (when in a git checkout), ensures a .env exists, then runs the setup wizard.
set -euo pipefail
cd "$(dirname "$0")"

log() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

if ! command -v uv >/dev/null 2>&1; then
    log "Installing uv (Python toolchain manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

log "Syncing dependencies (this also provisions Python 3.12)..."
uv sync

if [ -d .git ]; then
    log "Wiring git hooks..."
    uv run pre-commit install --install-hooks --hook-type pre-commit --hook-type commit-msg
fi

if [ ! -f .env ]; then
    log "Creating .env from template..."
    cp .env.example .env
fi

log "Launching setup wizard..."
uv run mika setup

log "Done. Start the bot with 'make run', or the settings page with 'make web'."
