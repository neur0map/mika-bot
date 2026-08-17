# web/routes/

HTTP route groups, one file per resource (`settings.py`, `overview.py`). Routes
validate input, call the persistence/service layer, and return schema models. The overview includes
content-free relationship-memory counts, policy state, checkpoint health, and degradation status.
