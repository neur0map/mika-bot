# ai/llm/ - inference

The path that turns a request + context into a reply. Part of the AI domain;
**never imports `discord.*`** and is usable headless. Depends on `core` (and
`persistence` for memory).

- `client.py` - high-level entry: request + context -> response.
- `providers/` - backend adapters behind the `ChatProvider` protocol.
- `chat/` - prompt assembly and the turn pipeline.
- `memory/` - conversation memory store and recall.
- `tools/` - function/tool-calling registry (tools the chat model may call).
