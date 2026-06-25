# llm/providers/

Backend adapters, one file per provider, all implementing `base.ChatProvider`.

- `base.py` - the `ChatProvider` protocol and `ChatMessage`.
- `openai_compatible.py` - OpenRouter / Groq / Together / OpenAI.

Adding a provider means adding a file; nothing upstream changes.
