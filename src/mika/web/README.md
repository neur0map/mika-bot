# web/

Backend for the localhost settings & overview page (FastAPI). Serves the API the
`frontend/` consumes. **Never imports `discord.*`** - it reads/writes through the
persistence layer and a service interface to the bot.

- `app.py` - the application factory.
- `routes/` - HTTP route groups, one file per resource.
- `schemas/` - pydantic request/response models.
- `conversation_diagnostics.py` - aggregate-only trace and benchmark read model. It must
  never return conversation content or Discord identifiers.
