#!/usr/bin/env bash
# Update the bot to a new release, safely - keeps your .env, memory and persona.
# Usage: ./update.sh path/to/mika-NEW-VERSION.zip
set -euo pipefail
cd "$(dirname "$0")"

if [ "$#" -lt 1 ]; then
    echo "Usage: ./update.sh path/to/new-version.zip" >&2
    exit 1
fi

if [ -x ".venv/bin/mika" ]; then
    exec .venv/bin/mika update "$1"
fi
exec uv run mika update "$1"
