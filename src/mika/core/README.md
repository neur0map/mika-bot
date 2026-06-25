# core/

Cross-cutting foundations every other layer builds on. Imports nothing internal.

- `config.py` - typed settings from env/.env via `get_settings()`; the only place
  configuration is read.
- `logging.py` - `configure_logging()` and `get_logger()`.
- `errors.py` - the `MikaError` hierarchy; catch these, never bare `Exception`.
- `paths.py` - resolved runtime paths (data dir, ...).
