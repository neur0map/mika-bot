# Mikav2 changelog

## Unreleased

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
