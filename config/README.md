# config/

Deployment configuration the operator edits. Not secrets - those live in `.env`.

- `persona.md` - the bot's character / base system prompt. Edit freely. The
  user-facing **display name** is set via `MIKA_PERSONA_NAME`. This file plus that
  variable are the **only** place the bot's identity is defined; code never
  hardcodes a name.

Referenced by `MIKA_PERSONA_FILE` (see `../.env.example`) and loaded by
`src/mika/ai/llm/chat/prompt.py`.
