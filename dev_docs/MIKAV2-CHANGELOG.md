# Mikav2 changelog

## 2026-07-19 — Conversation pipeline audit and social-turn reliability

- Audited 241 retained Mikav2 decisions and identified the main live quality failures:
  64 replies exceeded 120 characters, 16 exceeded 200, and the longest casual
  reply reached 643 characters; 45 recent turns fell back from the structured
  turn contract; and only one of five incoming-media turns selected a reaction or
  media action.
- Restricted web-tool access to current/factual requests (weather, news, current
  scores, prices, etc.). Casual banter and jokes now go directly through JSON-mode
  structured-turn generation instead of disabling JSON mode by loading tool schemas.
- Added `silence` as a valid `mika_turn.v2` intent. An intentional no-action turn
  is no longer rewritten into the visible `brain snagged` failure message.
- Updated the Discord executor so silent turns create decision telemetry but do not
  send a Discord reply or archive a fake assistant chat message.
- Added a social reply budget: chat, jokes, sarcasm, flirting, hype, criticism, and
  media reactions are capped at 180 characters; longer explanation-oriented turns
  retain a 500-character ceiling.
- Tightened the live persona/turn contract around concise Discord behavior, rare
  filler phrases, selective silence, reaction/GIF opportunities, and no captioning
  of incoming GIFs/images unless asked.
- Added regression coverage for explicit silence, joke/banter tool suppression,
  current-fact tool allowance, and the social reply-length cap.

## 2026-07-08 — MiniMax structured-output and GIF routing hotfix

- Requested OpenAI-compatible JSON object mode for structured turn generation
  and malformed-output repair retries so MiniMax M3 is less likely to fall back
  into plain Discord text.
- Disabled web-search tool routing for direct GIF/sticker/clip requests; Mika now
  treats those as media actions instead of searching the web for GIF pages.
- Added a small imperative media fallback for requests like "send a gif of X" so
  Klipy still receives a clean media query when the model forgets the `media`
  field.
- Added an outgoing media gate so MiniMax cannot attach random GIFs to plain
  factual/chat answers unless the user requested media or the turn has a confident
  social media-worthy intent.
- Added regression coverage for JSON-mode requests, media-request tool routing,
  GIF media forcing, and random-media suppression.

## 2026-07-07 — Social persona guardrails from Discord research

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
