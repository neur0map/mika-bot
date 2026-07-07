# Mikav2 changelog

## Unreleased

### Turn intent telemetry

- Added `mika_turn.v2` fields for `intent` and `confidence` so joke, sarcasm,
  flirt, hype, comfort, criticism, serious, and media-reaction decisions can be
  audited after live chats.
- Stored the schema version, intent, and confidence in shared turn telemetry.
- Kept user-visible Discord replies unchanged; the new fields are for behavior
  analysis and self-improvement only.
