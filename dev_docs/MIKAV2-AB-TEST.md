# Mikav2 side-by-side A/B test

Mikav2 can run beside the older JavaScript Mika bot without replacing it. The
setup is meant for comparing real Discord behavior, not for an in-place migration.

## Runtime boundaries

- Keep each bot on its own Discord application, token, container, and local data
  directory.
- Mikav2 can run in chat-only mode with `MIKA_COMMANDS_ENABLED=false`; this skips
  slash-command registration and avoids command collisions with the incumbent bot.
- Keep the older bot running while Mikav2 is tested. Shared storage is only for
  evaluation data and semantic memory, not operational state.

## Shared evaluation logs

Set `MIKA_SHARED_ARCHIVE_PATH` when Mikav2 should write into the same
JS-compatible archive used by the older bot. Mikav2 writes:

- message rows with `metadata.source = "mikav2-python"`
- assistant rows linked to the triggering Discord message
- `mikav2_turn_decision` training events with reply length, reaction choices, and
  media choices
- reaction feedback events from human users

Mikav2 still keeps its own local SQLite database for recent chat context. That
prevents schema collisions while still letting both bots share a durable archive
and Honcho workspace/session for evaluation.

## Reply, reaction, and media decisions

The LLM client asks the model for a structured turn:

```json
{
  "schema_version": "mika_turn.v2",
  "reply": "short Discord-native text",
  "reactions": ["💀"],
  "media": {"type": "none", "query": null},
  "intent": "sarcasm",
  "confidence": 0.82
}
```

The Discord event handler sends the reply, adds at most one reaction, optionally
searches Klipy for GIF/sticker/clip media, then records the outcome in the shared
archive. This makes tone, reaction timing, GIF judgment, social intent, and
confidence measurable.

Incoming GIFs, stickers, images, and embeds are passed to the LLM as compact
social context. Mikav2 should decide whether the media reads like a joke,
sarcasm, flirting, hype, reaction bait, or a serious share. She should not
caption or describe the GIF unless someone asks; the expected decision is whether
to answer with text, add a reaction, match with a GIF/sticker/clip, or stay dry.
The turn telemetry now records inbound media count and the compact context so GIF
and reaction misses can be audited later.

## Output-leak guard

Some models occasionally leak labels such as `reply:` or `media: none` into the
visible Discord message. The parser now strips those labels and keeps only the
actual reply text. A regression test covers the observed failure:

```text
ugh tell me about it ... reply: exactly, the pasta is a 10 ... media: none
```

The sent reply becomes only the text after `reply:` and before `media:`.

## Flirty and funny tone

Mikav2 should be able to read flirting and comedy as social energy, not as a
literal instruction. When users are playful, she can answer with coy teasing,
witty confidence, callbacks, dry one-liners, and light roasts. If the room is not
flirting, she should not force it or drop random pickup-line energy. Flirting
stays suggestive in tone rather than explicit or creepy: never possessive, no
jealousy, no guilt, and no emotional dependency.

## Discord social selectivity

Mikav2 should not act like every public message is hers to answer. In public
channels she stays less intimate, shorter, and more selective. If she is not
mentioned, replied to, or clearly invited by the room, silence, a single
reaction-only turn, or no action is usually better than hijacking a human-to-human
conversation. DMs and direct replies can be warmer, but still not needy.

## Heated chat tone

Mikav2 should not sound like a corporate safety notice when Discord chat gets
edgy. The persona guidance asks for dry, human banter: tease the person or their
behavior in the room, avoid lectures and disclaimers, and avoid blanket claims
about races, nationalities, or ethnic groups. This keeps the bot natural without
turning it into a group-targeting amplifier.

## Verification checklist

Before deploying a Mikav2 behavior change:

1. Run ruff, mypy, and pytest locally.
2. Rebuild and restart only the Mikav2 container.
3. Verify the older Mika container is still up.
4. Check startup logs for Discord gateway and Honcho success.
5. Run a parser smoke test for any observed malformed model output.
6. Confirm the shared archive records both user and assistant rows.
