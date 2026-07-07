# Mikav2 changelog

## Unreleased

### Social persona guardrails

- Added explicit prompt rules that playful flirting must stay non-possessive,
  non-jealous, non-guilting, and free of emotional-dependency cues.
- Added public-channel selectivity rules so Mika avoids hijacking human-to-human
  conversations and can choose no action or a reaction-only turn when uninvited.

### Social turn contract fixtures

- Added golden tests for sarcasm, flirting, and media-reaction structured turns so
  future prompt/parser changes cannot silently break the core social action shape.

### Reaction/media-only turns

- Allowed structured turns with an empty reply when a reaction or media action is
  enough, avoiding forced `...` placeholder messages.
- Archived action-only turns with synthetic action ids and `actionOnly` telemetry
  so they remain visible in training logs.

### Structured-output retry

- Added one bounded retry when the first model response leaks labels or falls back
  to plain text instead of valid `mika_turn.v2` JSON.
- Kept the original cleaned reply if the retry also fails, avoiding blank or worse
  user-visible output.

### Turn parse status telemetry

- Added `parse_status` to structured turn results and shared telemetry so live
  audits can separate clean JSON, labeled-output cleanup, and plain fallback.

### Media query normalization

- Shortened and cleaned model-generated GIF/sticker/clip queries before calling
  Klipy so search terms stay mood/action based instead of caption-like.
- Added tests for URL stripping, punctuation cleanup, and empty-noise handling.

### Balanced turn JSON extraction

- Replaced greedy regex turn extraction with a balanced JSON-object scanner so
  fenced JSON, nested media objects, and braces inside strings parse reliably.
- Added regression coverage for prose-wrapped JSON and multiple-object outputs.

### Reaction feedback signals

- Normalized reaction telemetry into coarse learning signals: positive, laugh,
  confused, negative, and other.
- Stored the signal beside raw emoji data so later reflection can distinguish a
  laugh reaction from approval or confusion.

### Live self-reflection lessons

- Fed the latest stored self-reflection lessons into the live system prompt next
  to recalled memory so the learning loop changes future replies.
- Kept reflection lessons separate from user recall to make the prompt source
  auditable.

### Repetition pressure

- Added recent-assistant wording hints to the live generation input so responses
  avoid repeating the same rhythm, joke shape, and phrasing across a channel.
- Kept the stored user memory clean by not writing the anti-repetition hints into
  local or Honcho memory.

### Turn intent telemetry

- Added `mika_turn.v2` fields for `intent` and `confidence` so joke, sarcasm,
  flirt, hype, comfort, criticism, serious, and media-reaction decisions can be
  audited after live chats.
- Stored the schema version, intent, and confidence in shared turn telemetry.
- Kept user-visible Discord replies unchanged; the new fields are for behavior
  analysis and self-improvement only.
