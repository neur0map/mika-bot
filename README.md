# Mika

A self-hostable Discord conversation companion. It listens only where you allow it,
answers mentions or selected free-chat channels, and can use concise reactions or media
when appropriate. The local, login-gated dashboard manages its configuration.

Built in Python for Linux VPS deployment.

> **License:** proprietary, source-available on purchase — see [`LICENSE`](LICENSE).

## Quickstart

```bash
./install.sh
make run
```

The setup wizard stores deployer-provided Discord and model credentials in `.env`.
Use `make chat` to test the model without Discord and `make doctor` to check the setup.

## How it responds

- Mention it in any allowed server channel for a response.
- Configure `DISCORD_RESPONSE_CHANNEL_IDS` for dedicated free-chat channels.
- Direct questions receive a concise answer; unrelated conversation can remain silent.
- GIF/sticker/clip search is optional and requires a Klipy key.

## Documentation

| Guide | What it covers |
|---|---|
| [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) | Installation and everyday operation |
| [docs/DISCORD-SETUP.md](docs/DISCORD-SETUP.md) | Bot credentials, intent, invite, and channel scope |
| [docs/DASHBOARD.md](docs/DASHBOARD.md) | Local settings and conversation-health dashboard |
| [docs/COSTS.md](docs/COSTS.md) | Model and optional service costs |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Host and Docker deployment |
| [docs/COMMAND-CLEANUP.md](docs/COMMAND-CLEANUP.md) | One-time stale Discord command removal |

## Development

```bash
make check
```

The repository is layered; see [ARCHITECTURE.md](ARCHITECTURE.md) and contributor
requirements in [AGENTS.md](AGENTS.md).
