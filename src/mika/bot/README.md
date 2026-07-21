# bot/

The Discord bot-account domain contains the event lifecycle and conversational execution layer.

- `client.py` creates the Discord client and starts conversation services.
- `events/` handles ready, messages, and reaction feedback.
- `media.py` executes selected GIF/sticker/clip actions.
- `scheduler.py` runs optional learning/reflection jobs.

Discord user-facing behavior is conversation-only. Operator commands belong under `mika.cli` and are not Discord commands.
