# llm/

All LLM work, usable without a Discord bot. **Never imports `discord.*`.**
Depends on `core` (and `persistence` for memory).

- `client.py` - high-level entry: request + context -> response.
- `providers/` - backend adapters behind the `ChatProvider` protocol.
- `chat/` - prompt assembly and the turn pipeline.
- `memory/` - conversation memory store and recall.
- `tools/` - function/tool-calling registry.
