# bot/features/ - server features

Self-contained, pluggable **server** feature modules - one folder per feature, part
of the server (bot-account) domain. A feature owns its commands, events, components,
and persistence wiring, enabled per guild.

- `tickets/` - support ticket system.
- `moderation/` - moderation + anti-spam.

Adding a feature = adding a folder. Depends on `core`, `persistence`, and the
bot/ai interfaces.
