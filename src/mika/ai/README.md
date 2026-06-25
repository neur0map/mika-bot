# ai/ - AI domain

Everything model- and learning-related, shared by the bot and (optionally) the
userbot. Depends on `core` and `persistence` only.

- `llm/` - inference: providers, chat orchestration, memory, tools. The path that
  produces a reply. Never imports `discord.*`.
- `learning/` - the **optional** self-learning system: reviews past interactions
  with the Hermes agent and distills durable lessons. Off by default.
