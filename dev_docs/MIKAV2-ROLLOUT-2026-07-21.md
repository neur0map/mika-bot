# Python Mika rollout — 2026-07-21

## Release

- Conversation-only runtime and non-chat automation removal were deployed to the Python `mika` Compose service.
- Selected deployment model: `openai/gpt-5.4-mini` through the configured OpenRouter-compatible route.
- The deprecated JS container remains stopped.

## Preflight evidence

- Local gate: Ruff, format check, mypy, and 51 pytest tests passed.
- VPS source/config backup: `/opt/bot-backups/mikav2-pre-rollout-20260721144610`.
- Stopped-image smoke returned a strict `json_schema` response format.
- Shared archive mounted and opened read-only.
- Stale Discord application-command cleanup completed with 0 global and 0 configured-guild commands remaining.

## Live verification

- Python `mika` container started successfully.
- Discord gateway connected as `MikaV2#2805`.
- The container resolves `honcho-api-1`; its Honcho health endpoint returned HTTP 200.
- The Python watchdog was updated for the current container/model and passed an immediate forced run.

## Measurement discipline

The archived baseline remains 241 decisions, including 45 fallback turns and 64 replies above 120 characters. The controlled provider smoke favored GPT-5.4 mini over MiniMax M3 for strict turn compliance. This rollout record does not claim post-rollout conversational quality: a natural live cohort is required before scoring reply length, structured fallback, media behavior, or reflection outcomes.
