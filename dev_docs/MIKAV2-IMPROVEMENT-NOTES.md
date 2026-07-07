# Mikav2 improvement research notes

## Sources reviewed so far

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

## Medium-value changes

1. Add a bounded retry when the structured turn is invalid or too repetitive.
2. Add media-query normalization so GIF searches use short mood/action queries.
   - Status: implemented in the shared Klipy search helper.
3. Add small golden-fixture tests for sarcasm, flirting, media-only messages, and
   criticism handling.
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
