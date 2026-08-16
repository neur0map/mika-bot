# Optional: long-term memory with Honcho

Your bot already has local cross-session memory: recent channel history,
explicit facts that users state about themselves, same-user/channel lexical
recall, and aggregate feedback from reactions to Mika's messages. **Honcho** adds
optional semantic recall on top. It needs **Docker**; everything else works
without it.

## Easiest: let the bot set it up for you

With Docker installed, one command fetches, builds, and starts Honcho:

```
mika honcho up
```

The first run downloads and builds it (a few minutes); after that it's instant.
Then make sure it's enabled — either you answered **yes** to the Honcho question
during `mika setup`, or run `mika setup` again and choose yes.

Check it worked:

```
mika doctor      # the "Honcho memory" row should say PASS
```

Stop it anytime with `mika honcho down`, check it with `mika honcho status`.

## Manual setup (if you'd rather)

```bash
git clone https://github.com/plastic-labs/honcho
cd honcho && cp docker-compose.yml.example docker-compose.yml
cp .env.example .env        # set LLM_OPENAI_API_KEY
docker compose up -d --build
```

Then set in your bot's `.env`: `MIKA_MEMORY_HONCHO_ENABLED=true` and
`MIKA_MEMORY_HONCHO_BASE_URL=http://127.0.0.1:8000`.

## Good to know

- If Honcho is ever down, the bot **automatically falls back** to local memory —
  it never breaks your bot.
- Local facts are scoped by Discord user ID and corrections replace the prior
  value for the same fact key. Trace diagnostics store counts only, not fact or
  message text.
- Honcho's memory engine needs its own LLM key; `mika honcho up` reuses your bot's
  key. If you use a non-OpenAI provider and see derivation errors, adjust the
  provider settings in `var/honcho/.env`.
