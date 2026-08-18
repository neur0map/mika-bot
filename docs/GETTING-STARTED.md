# Getting started

Mika is a self-hosted Discord conversation companion. She responds to direct mentions, DMs, and configured free-chat channels with selective text, reactions, GIFs, or intentional silence.

## Requirements

- Python 3.12 and `uv`, or Docker Compose
- A Discord bot application with the `bot` scope and message-content intent
- An LLM provider configured in `.env`

## Install

```bash
make install
cp .env.example .env
mika setup
make run
```

For Docker deployments, configure `.env` and run:

```bash
docker compose up -d --build mika
```

## Discord scope

Invite the bot with the `bot` scope and permissions appropriate for conversation: view channels, send messages, read message history, add reactions, embed links, and attach files. Mika has no Discord slash-command product.

## Conversation behavior

- Mention Mika for a direct response.
- Configure free-chat channels if she should participate without a mention.
- Mika may answer with text, react, send a fitting GIF, or stay quiet.
- Configure model, memory, reflection, and media providers through the operator CLI or dashboard.

## Troubleshooting

- If Mika does not reply, verify the bot token, message-content intent, allowed guild/channel scope, and LLM provider configuration.
- If media actions do not send, verify the configured media provider and Discord attachment permissions.
- Use `mika web` for local operational status and `mika cleanup-commands --help` only when migrating an older installation with stale registered commands.

## Verify relationship memory

Run the deterministic held-out benchmark before enabling or deploying relationship-memory changes:

```bash
uv run python tools/run_relationship_memory_benchmark.py --mode all
```

The command benchmarks the isolated relationship service and affinity-retriever components, not the
complete production `ManagedSocialMemory` and merged Honcho composition. Local hybrid remains
informational until Mika has a configured embedding scorer. The
lexical rollout gate requires zero cross-scope leakage, at least 95% correction adoption, at least
98% correct-person attribution, and measured wall-clock local p95 retrieval below 100 ms.
Content-free aggregate JSON and per-case JSONL are written under `var/benchmarks/`. The Honcho mode
is included only when Honcho is configured and remains informational.

Accepted visible observations use a private (`0600`) local spool and expire after 24 hours by
default (`MIKA_MEMORY_RELATIONSHIP_SPOOL_TTL_SECONDS`). Retries drain automatically without a
restart. Dead letters retain content-free status only; their message payload is purged. Operator
health reports operation and per-phase p95 latency, and treats failures, retries, and dead letters
as unhealthy outcomes.
