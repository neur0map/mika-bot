# bot/ - server domain (the bot account)

The compliant, sellable core: a Discord **bot account** that serves everyone in a
guild. Wires the gateway and routes interactions/events into `ai/` and `features/`.

- `client.py` - intents, command registration, event wiring.
- `commands/` - server slash commands everyone can use, one file each.
- `events/` - gateway event handlers, one file each.
- `components/` - buttons, modals, views.
- `features/` - pluggable server features (tickets, moderation, ...).

Depends on `core`, `persistence`, `ai`. Must **never** import `userbot/`.
