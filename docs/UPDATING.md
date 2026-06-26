# Updating

New versions arrive as a zip - new commands, fixes and improvements. Updating is safe:
your login, settings, conversation memory and persona are all kept.

## One command

From your bot's folder:

```bash
./update.sh path/to/mika-NEW-VERSION.zip
```

(or `mika update path/to/mika-NEW-VERSION.zip`). It will:

1. **Back up** your current version (into `var/backups/`).
2. **Swap in** the new code - your `.env`, your `var/` folder (memory, database, logs)
   and your active persona are left untouched.
3. **Reinstall** dependencies.
4. **Restart** the background service (if you installed one) so new slash commands sync
   to Discord automatically.

If you run the bot in the foreground instead of as a service, just start it again
(`mika run`) after updating.

## Rolling back

Every update prints a backup path. To go back to the previous version, from your bot's
folder:

```bash
tar xzf var/backups/pre-update-<timestamp>.tgz
```

then restart. Your data is never in that backup - it was never touched.

## Notes

- New slash commands show up in Discord a moment after the restart. If one is missing,
  wait a minute (Discord caches them) or run `mika doctor`.
- Updating never changes your `.env`; if a new version adds a setting, it uses a sensible
  default until you set it (in the dashboard or `mika setup`).
