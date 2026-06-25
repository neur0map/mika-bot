# ai/llm/chat/

Chat orchestration.

- `prompt.py` - system-prompt and persona assembly from settings, memory, and
  lessons distilled by `ai/learning/`.
- `pipeline.py` - the turn pipeline: gather context, build prompt, call a provider,
  shape the reply.
