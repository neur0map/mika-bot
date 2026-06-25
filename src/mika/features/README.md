# features/

Self-contained, pluggable feature modules - one folder per feature. A feature owns
its own commands, events, components, and persistence wiring, and exposes a small
entry the bot enables per guild. Depends on `core` and the bot/llm interfaces.

- `tickets/` - support ticket system.
- `moderation/` - moderation + anti-spam.

Adding a feature means adding a folder.
