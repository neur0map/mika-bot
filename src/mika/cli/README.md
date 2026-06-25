# cli/

The `mika` command (Typer) - the operator entrypoint and setup wizard.

- `app.py` - assembles the command tree; `main()` is the console-script target.
- `commands/` - one file per command: `run`, `web`, `setup`, `service`.

This layer orchestrates the others; keep real logic in those layers, not here.
