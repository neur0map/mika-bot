# Mikav2 improvement notes

## 2026-07-08 live-log follow-up

- Live MiniMax M3 logs showed successful OpenRouter calls but `fallback` parse
  status in Mikav2 telemetry, meaning answers were being accepted as unstructured
  text after the model missed the JSON contract.
- GIF-like prompts were routed through `web_search` (`watch me whip ... gif` web
  queries) instead of the Klipy media action path.
- Fix direction: require JSON object mode where provider-compatible, perform
  repair retries without tools, and route explicit GIF/sticker/clip requests away
  from web search toward media selection.
- Dry-run after that fix showed MiniMax could still attach a GIF to a plain math
  answer, so outbound media now passes a final intent/confidence gate before
  Discord send.

## Research-backed priorities

- Structured output best practices: schema-first design, validation at the model
  boundary, bounded enums/arrays/strings, and schema versioning.
  <https://llmbestpractices.com/ai-agents/structured-output>
- Production structured-output guidance: small closed schemas, runtime validation,
  bounded retries, schema versions, and attempt/failure observability.
  <https://techbytes.app/posts/structured-outputs-production-schema-retry-validation/>
- Discord developer docs: reactions require the right gateway events/intents and
  should be treated as low-friction social/action signals.
  <https://docs.discord.com/developers/quick-start/getting-started>
- Reflective Memory Management: topic-based reflection and response-time feedback
  improve long-term personalized dialogue memory.
  <https://aclanthology.org/2025.acl-long.413.pdf>
- AdaMem: dialogue agents benefit from separating recent working memory,
  episodic/persona memory, and question-conditioned retrieval.
  <https://www.arxiv.org/pdf/2603.16496>
- Dynamic Persona Coherence: good roleplay separates stable identity from adaptive
  short-term affect so characters can react without drifting or becoming rigid.
  <https://aclanthology.org/2026.acl-long.1336.pdf>
- Role-playing evaluation research: useful evaluations include emotional
  understanding, decision-making, consistency, entertainment value, human-likeness,
  and long-session coherence rather than one-turn quality only.
  <https://ar5iv.labs.arxiv.org/html/2505.13157>
  <https://arxiv.org/html/2409.06820v4>
  <https://arxiv.org/html/2605.29256>
- Conversation tone and Discord bot UX guidance: keep voice stable while tone
  adapts, stay short in public channels, use reactions as turns, and avoid noisy
  bot participation.
  <https://www.nngroup.com/articles/tone-of-voice-dimensions/>
  <https://wildandfreetools.com/blog/system-prompt-discord-telegram-whatsapp-bot/>
- Responsible persona design: playful companion behavior should avoid
  possessiveness, jealousy, hidden dependency cues, manipulative guilt, and false
  intimacy.
  <https://www.microsoft.com/en-us/research/wp-content/uploads/2018/11/Bot_Guidelines_Nov_2018.pdf>
  <https://someones.xyz/design-principles-for-emotionally-safe-avatars-and-bots>
- Agent workflow guidance: prefer bounded workflow stages, typed outputs,
  validation, and evaluation loops before adding open-ended autonomy.
  <https://www.anthropic.com/engineering/building-effective-agents>

## High-value changes

1. Version and validate the structured turn contract.
   - Reason: Mikav2 already relies on structured turn decisions, but the contract
     needs versioned metadata for debugging and future migrations.
   - Status: implemented with `mika_turn.v2`, `intent`, and `confidence`.
2. Pass incoming media as social context, not invisible attachments.
   - Reason: GIF-only or embed-heavy messages need a joke/sarcasm/flirt/media
     decision instead of captioning or ignoring.
   - Status: implemented before this note; kept as a core A/B-test behavior.
3. Add repetition pressure from recent assistant replies.
   - Reason: repeated phrasing is one of the fastest ways a companion bot feels
     scripted. Recent assistant text should steer generation away from repeats.
   - Status: implemented with recent assistant phrasing hints that are not stored
     back into memory.
4. Feed reflection lessons back into the live prompt.
   - Reason: existing reflection stores lessons, but live replies do not read them,
     making self-learning mostly cosmetic.
   - Status: implemented by adding the latest stored reflection as a separate live
     prompt context section.
5. Add lightweight reaction feedback interpretation.
   - Reason: raw reactions are logged, but self-learning needs coarse positive,
     negative, confused, hype, and laugh signals.
   - Status: implemented as positive, laugh, confused, negative, and other signals
     stored in reaction telemetry.
6. Support reaction/media-only turns.
   - Reason: a human often answers a GIF or joke with only an emoji or matching GIF;
     forcing a text reply makes the bot feel less reactive.
   - Status: implemented without dropping archive/telemetry rows.

## Medium-value changes

1. Add a bounded retry when the structured turn is invalid or too repetitive.
   - Status: implemented for invalid/non-JSON turn outputs; repetitive wording is
     handled by recent-phrase pressure rather than extra retries.
2. Add media-query normalization so GIF searches use short mood/action queries.
   - Status: implemented in the shared Klipy search helper.
3. Add small golden-fixture tests for sarcasm, flirting, media-only messages, and
   criticism handling.
   - Status: implemented initial deterministic fixtures for sarcasm, flirting, and
     media-reaction structured turns.
4. Add log fields for schema version and parse fallback rate.
   - Status: implemented with `schemaVersion` and `parseStatus` in turn telemetry.
5. Avoid greedy regex extraction for model JSON.
   - Status: implemented with balanced object extraction and parser tests.

## Low-value or defer

1. Full graph memory or multi-agent memory routing.
   - Valuable long-term, but too heavy for the current repo and live bot needs.
2. Provider-specific strict JSON schema mode.
   - Worth adding later, but OpenRouter/model compatibility should be tested per
     provider before relying on it in production.
3. Buttons/components for feedback.
   - Useful for product UX, less urgent than fixing natural chat tone and media
     reactivity.

## Future candidates

1. Lightweight session affect tracking.
   - Dynamic persona research suggests separating stable identity from short-term
     affect. Mikav2 now logs intent/confidence; a later pass can summarize recent
     turn intents into a room mood without adding heavy psychological state.
2. Session-level evaluator fixtures.
   - Roleplay evaluation work shows single turns miss long-horizon drift,
     repetition, and loss of persona. A later CI eval can simulate 6-10 turns and
     score consistency, entertainment, media timing, and repetition.
3. Selective exemplar memory.
   - Store only high-signal good replies or corrected misses as examples, not every
     raw turn, so retrieval improves style without bloating the prompt.
