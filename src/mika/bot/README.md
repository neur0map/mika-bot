# bot/

The Discord-facing layer. Wires the gateway and routes interactions/events into
the `llm` and `features` layers through their interfaces.

- `client.py` - intents, command registration, event wiring.
- `commands/` - slash commands, one file each.
- `events/` - gateway event handlers, one file each.
- `components/` - buttons, modals, views.
