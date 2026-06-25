# ai/learning/reviewer/

The reviewer that judges and improves interactions, backed by the external
**Hermes agent** (NousResearch). A separate brain from the chat model.

- `agent.py` - bridge to the Hermes agent (subprocess/HTTP) with a locked-down
  toolset and prompt, mirroring the hardened bridge in the reference material.
- `skills/` - skills the reviewer may apply (one file per skill).
- `tools/` - tools the reviewer may call (one file per tool).
- `rules/` - learning policies: confidence thresholds, what is safe to persist,
  privacy/secret filters, anti-drift checks.
