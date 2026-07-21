# Updating

1. Back up `.env`, `var/`, and any shared archive before replacing source.
2. Pull or install the new release.
3. Install dependencies with `uv sync` when dependencies changed.
4. Run the full verification gate:

```bash
make check
```

5. Build the stopped image and run non-Discord smoke checks.
6. Restart the Python `mika` service only after the image and smoke checks pass.

Mika is conversation-only. A restart does not register Discord application commands. For an installation upgraded from an older command-enabled release, use the explicit operator migration documented in [COMMAND-CLEANUP.md](COMMAND-CLEANUP.md).
