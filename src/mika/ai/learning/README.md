# ai/learning/ - self-learning system (optional, opt-in)

Observes interactions and improves the bot over time. **Off by default**, enabled
per guild/user via config. Uses the external **Hermes agent** as an independent
reviewer - the chat model never grades itself.

- `reviewer/` - the Hermes-agent reviewer plus its `skills/`, `tools/`, `rules/`.
- `feedback/` - capture signals (reactions, corrections, ratings) from bot and
  userbot interactions.
- `reflection/` - the scheduled self-improvement pass (the "nightly" job).
- `store.py` - persistence of distilled lessons / knowledge.

Flow: feedback -> reviewer (Hermes) applies rules -> distilled lessons -> store ->
fed back into prompt assembly (`ai/llm/chat/prompt.py`). The reviewer only
*suggests*; `reviewer/rules/` decide what is safe to keep. The Hermes agent is an
external dependency installed on the host; if absent, learning is a no-op.
