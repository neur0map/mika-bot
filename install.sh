#!/usr/bin/env bash
# One-command installer for the bot (for end users).
# Installs the uv toolchain if missing, installs the bot's dependencies, ensures a
# .env exists, creates a global `mika` command, then launches the setup wizard.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

# --- check prerequisites -----------------------------------------------------
if ! command -v curl >/dev/null 2>&1; then
    echo "This installer needs 'curl'. Install it first (e.g. 'sudo apt install curl'), then re-run." >&2
    exit 1
fi
command -v git >/dev/null 2>&1 || say "Note: 'git' isn't installed - recommended for updates, but not required."
if command -v docker >/dev/null 2>&1; then
    say "Docker detected - optional long-term memory (Honcho) is available. See docs/HONCHO-MEMORY.md."
else
    say "Docker not found - the bot runs fine without it. Install Docker later only if you want Honcho memory."
fi

if ! command -v uv >/dev/null 2>&1; then
    say "Installing uv (the Python toolchain)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

say "Installing the bot (this also sets up Python automatically)..."
uv sync --no-dev

[ -f .env ] || cp .env.example .env

# Create a global `mika` command so the bot runs without uv or activating a venv.
# It cd's into this folder first, so your .env and data are always found.
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/mika" <<LAUNCHER
#!/usr/bin/env bash
cd "$ROOT" || exit 1
exec "$ROOT/.venv/bin/mika" "\$@"
LAUNCHER
chmod +x "$BIN_DIR/mika"
say "Installed the 'mika' command to $BIN_DIR/mika"

# Make sure ~/.local/bin is on PATH for future terminals.
case ":${PATH}:" in
    *":$BIN_DIR:"*) ;;
    *)
        export PATH="$BIN_DIR:$PATH"
        for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
            [ -f "$rc" ] || continue
            grep -q 'added by mika installer' "$rc" 2>/dev/null && continue
            printf '\n# added by mika installer\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc"
        done
        say "Added $BIN_DIR to your PATH - open a new terminal once setup finishes."
        ;;
esac

# fish keeps PATH separately - add it there too if fish is present.
if command -v fish >/dev/null 2>&1; then
    fish_cfg="$HOME/.config/fish/config.fish"
    mkdir -p "$(dirname "$fish_cfg")"
    grep -q 'added by mika installer' "$fish_cfg" 2>/dev/null || \
        printf '\n# added by mika installer\nfish_add_path "$HOME/.local/bin"\n' >> "$fish_cfg"
fi

say "Starting the setup wizard..."
"$BIN_DIR/mika" setup

# If setup wrote a token, offer to bring the bot + dashboard up as a background service.
echo
if grep -qE '^DISCORD_TOKEN=.+' .env 2>/dev/null && ! grep -qE '^DISCORD_TOKEN=(CHANGEME)?$' .env; then
    read -r -p "$(printf '\033[1;36m==>\033[0m Start the bot + dashboard now in the background? [Y/n] ')" reply
    case "$reply" in
        [Nn]*) say "Skipped. Start later with: mika service install" ;;
        *) "$BIN_DIR/mika" service install ;;
    esac
fi

echo
say "Test the AI:        mika chat \"hello\""
say "Run in foreground: mika run"
say "Open the dashboard at the URL the wizard printed and log in."
