# persistence/

Storage layer - the only code that talks to the database. Depends on `core` only.

- `engine.py` - async engine + session factory built from `core.config`.
- `base.py` - the SQLAlchemy declarative base.
- `models/` - ORM models, one file per aggregate.
- `repositories/` - data-access objects, one file per aggregate.

Other layers call repositories; they never write raw SQL.
