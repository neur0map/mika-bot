# Optional: long-term memory with Honcho

Your bot already remembers recent conversation out of the box (its built-in local
memory). **Honcho** is an optional upgrade that adds *semantic* long-term memory —
it remembers people and facts across sessions and recalls what's relevant. It's
off by default because it needs Docker.

You only need this if you want deeper, cross-session memory. Skip it otherwise;
everything else works without it.

## 1. Run Honcho (needs Docker)

```bash
git clone https://github.com/plastic-labs/honcho
cd honcho
cp .env.example .env        # open .env and set LLM_OPENAI_API_KEY
docker compose up -d        # serves on http://127.0.0.1:8000
```

## 2. Turn it on for the bot

Add these to your `.env` (in the bot folder), then restart the bot:

```
MIKA_MEMORY_HONCHO_ENABLED=true
MIKA_MEMORY_HONCHO_BASE_URL=http://127.0.0.1:8000
MIKA_MEMORY_HONCHO_WORKSPACE=my-bot
MIKA_MEMORY_HONCHO_SESSION=main
```

## 3. Check it

```
mika doctor
```

The **Honcho memory** row should say **PASS**. From then on the AI blends Honcho
recall into its replies. If Honcho is ever down, the bot automatically falls back
to local memory — it never breaks your bot.
