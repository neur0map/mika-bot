# Discord history archive

This standalone operator tool preserves every Discord message visible to the configured bot, plus attachments and directly linked external resources. It is intentionally separate from Mika's runtime and never places archive data in Git.

Production data defaults to `/srv/mika-discord-archive`. See [`docs/DISCORD-ARCHIVE.md`](../../docs/DISCORD-ARCHIVE.md) for the storage, safety, cursor, and verification design.

Run from a checkout:

```bash
python3 -m venv /srv/mika-discord-archive/.venv
/srv/mika-discord-archive/.venv/bin/pip install -r tools/discord_archive/requirements.txt
MIKA_ARCHIVE_SOURCE="$PWD/tools/discord_archive" tools/discord_archive/archive sync --full
```

The tool reads Discord credentials from `/opt/mikav2-bot/.env` by default. It never logs or stores the bot token.

Commands:

- `archive sync --full`: initial complete history import.
- `archive sync`: cursor-based incremental import with bounded edit reconciliation.
- `archive download --workers 8`: retry and acquire pending external resources.
- `archive export`: rebuild deterministic training JSONL exports.
- `archive verify --online`: hash, database, stream, export, permission, and Discord-count verification.
- `archive status`: concise local counts and disk usage.
