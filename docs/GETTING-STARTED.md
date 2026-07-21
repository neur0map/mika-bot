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
