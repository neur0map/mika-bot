# Natural Expression Skill Design

Date: 2026-08-17
Status: awaiting implementation-plan review

## Purpose

Make Mika's conversational style feel less generated and more socially aware by treating emoji,
reactions, punctuation, and sentence rhythm as deliberate social choices. Mika should use standard
and server-specific emoji occasionally, understand what custom emoji mean even when their names are
misleading, and avoid repeating conspicuous habits across nearby replies.

The skill improves expression selection; it does not replace the participation planner, persona,
provider, memory system, or structured turn contract.

## Evidence-based revision

An analysis of 12,031 human messages and 679 assistant messages from the local server archive changed
the design priority. Human messages had a five-word median, used emoji in 4.4% of messages, used em
dashes in 0.14%, and contained multiple sentences in 2.5%. Assistant messages had an eight-word
median, used emoji in 30.2%, used em dashes in 1.77%, and contained multiple sentences in 18.6%.

Emoji reuse also occurred naturally among humans, so a fixed cooldown would manufacture a different
kind of artificial behavior. The primary feature is therefore a learned human-style distribution;
emoji intelligence and repetition penalties operate beneath that distribution.

## Observed production problem

Recent production replies repeatedly used the same small set of inline emoji, particularly smirking
and relieved faces, and repeatedly relied on em-dash constructions. The existing generation hint
includes recent assistant messages but does not extract or score stylistic fingerprints. The system
prompt encourages concise teasing and emoji reactions without defining abstention, cooldowns, or
community-specific meaning.

The root issue is therefore not a missing banned-character list. Mika lacks a stateful expression
policy between social intent and final generation.

## Goals

- Prefer no emoji unless one contributes tone, compression, or social alignment.
- Choose between inline emoji, a Discord reaction, custom media, and no expression deliberately.
- Support the broad Unicode emoji vocabulary without encouraging indiscriminate use.
- Discover all usable guild emoji and preserve their identity by Discord snowflake, not name.
- Infer custom emoji meaning from visual appearance and real server usage.
- Adapt cautiously to server culture and individual usage without overfitting to one person.
- Vary conspicuous punctuation, openings, sentence rhythm, joke shapes, and flirt cadence.
- Keep every learned meaning inspectable, correctable, confidence-scored, and reversible.
- Add negligible latency to ordinary turns after background profiling is complete.

## Non-goals

- Training or fine-tuning the primary language model.
- Generating or uploading new server emoji.
- Treating emoji selection as mandatory sentiment decoration.
- Copying every user's punctuation, slang, hostility, or identity-sensitive language.
- Giving the language model unrestricted access to the complete emoji catalog every turn.
- Replacing existing safety, participation, memory, or Discord permission checks.

## Design principles

1. **Abstention first.** No emoji is a real candidate and remains the default.
2. **Meaning and permission are separate.** Mika may understand an expression without being allowed
   to use it.
3. **Names are weak evidence.** A custom emoji's snowflake is its stable identity; visual content and
   community usage determine meaning.
4. **Evidence remains interpretable.** Profiles retain summaries, counts, timestamps, confidence,
   and contradiction signals rather than opaque final labels.
5. **Cooldowns are contextual penalties, not bans.** Strong context can justify repetition.
6. **Server culture is primary; personal adaptation is bounded.** One person's usage cannot silently
   redefine an emoji for everyone.
7. **Learning is background work.** Visual analysis and archive aggregation do not delay replies.

## Architecture

The bounded skill lives under `src/mika/conversation/skills/natural_expression/`:

```text
natural_expression/
  README.md
  contracts.py
  skill.py
  situation.py
  human_style.py
  unicode_catalog.py
  guild_catalog.py
  visual_profile.py
  usage_learning.py
  selector.py
  style_ledger.py
```

`NaturalExpressionSkill` accepts a turn context and returns compact `ExpressionGuidance`. It does
not send Discord messages or invoke the provider. The generation service incorporates the guidance
before requesting the structured turn. The action planner validates the returned reply and reaction
against the decision so malformed or hallucinated custom emoji cannot bypass the skill.

The initial implementation uses deterministic scoring around Mika's existing structured intent. A
small local vision-text embedding model may produce visual evidence in a background profiler. A
second generative intent model is explicitly deferred because it would add latency and another
failure boundary before evidence shows the deterministic classifier is insufficient.

The style target blends server, channel, and person profiles. Server evidence has the highest weight,
channel evidence adjusts local formality and rhythm, and the current person's profile contributes a
bounded adjustment. Mika does not imitate one person's vocabulary or identity markers.

Profiles contain aggregate statistics, never message bodies: message and word-length quantiles,
sentence count, emoji and custom-emoji rate, punctuation rates, casing, and normalized opening
frequencies. Runtime prompts receive a compact target range rather than example messages.

## Core contracts

### Emoji identity

`EmojiIdentity` contains:

- `kind`: `unicode` or `guild`
- `value`: Unicode grapheme or Discord emoji snowflake
- `guild_id` for custom emoji
- current Discord name, animation flag, availability, and role restrictions
- CDN content hash and cached asset path for custom emoji

Names are mutable metadata. Renames update the catalog without creating a new semantic profile.
Deleted or unavailable emoji remain in historical profiles but are not eligible for output.

### Semantic profile

`EmojiProfile` contains:

- visual description
- ranked social intents and emotions
- inline/reaction suitability
- public/private suitability
- safety labels
- positive, negative, and contradictory evidence counts
- server confidence and bounded per-person adjustments
- first-seen, last-seen, last-profiled, and model-version timestamps
- operator correction and lock state

Profiles are stored in additive database tables. Raw image data stays in the local data directory;
only paths, hashes, descriptions, and embeddings are stored in the database.

### Expression guidance

The generator receives a small object containing:

- social situation and confidence
- whether emoji should be avoided, optional, or encouraged
- up to three eligible candidates with placement and meaning
- recently overused emoji families and punctuation patterns
- one concise style instruction

Example:

```text
Situation: warm teasing, medium confidence.
Emoji: optional; prefer reaction over inline.
Avoid recently repeated smirk/relieved-face family and em-dash cadence.
Candidate: <:side_eye:123> — skeptical amusement, server confidence 0.87.
```

The prompt never receives the full catalog or raw historical evidence.

## Situation assessment

The assessor derives a bounded `SocialSituation` from existing turn data:

- structured intent
- direct address, reply target, participation mode, and channel type
- conversation language
- recent sentiment and intensity
- relationship affinity and recent feedback when available
- presence of incoming media, inline emoji, reactions, sarcasm, or criticism

It outputs emotion, interaction mode, intensity, public/private sensitivity, and confidence. Low
confidence reduces expression rather than selecting a generic emoji.

## Unicode catalog

The Unicode catalog groups emoji by semantic families rather than presenting a flat list. Seed data
comes from the Unicode emoji definitions available to the installed Python stack, with local curated
metadata for conversational meaning, ambiguity, placement, and safety.

The catalog supports all recognized emoji grapheme sequences but only promotes contextually suitable
candidates. Skin-tone and gender variants inherit their base semantics while remaining distinct
graphemes. Mika does not select identity-marked variants to imitate a user unless an operator sets a
server preference.

## Guild emoji discovery and visual profiling

On guild readiness and subsequent guild-emoji update events, the catalog synchronizes Discord emoji
objects the bot can see. Discord snowflake, name, animation, availability, role restrictions, and CDN
asset are recorded.

Static emoji use one rendered WebP image. Animated emoji are decoded and represented by bounded
samples: first, middle, final, and the frame with greatest visual change. The profiler generates:

- a literal visual description
- candidate emotion and social-intent labels
- a visual embedding
- confidence and model version

Visual evidence is an initial prior, not ground truth. Abstract reaction images and server in-jokes
remain low confidence until contextual evidence accumulates. Assets are reprocessed only when their
content hash or profiler version changes.

## Learning from server history

The weekly archive provides historical observations without becoming a live runtime dependency. The
learner processes:

- human-authored inline Unicode and custom emoji
- reactions attached to messages
- preceding and target message context
- language, channel, author, and timestamp
- positive or negative reactions to Mika's own expression choices

Evidence updates are aggregate and incremental. A durable cursor records the highest processed
archive event so weekly jobs only process new material. The source archive remains immutable.

Server evidence has the strongest learned weight. Per-person adjustments are capped and require a
minimum observation count. Time decay reduces stale meanings, while an immutable audit record keeps
the reason for profile changes inspectable.

No private-message content is added to a guild-wide definition. Profiles learned from private
contexts remain private-scoped. Raw message content is not duplicated into the profile tables.

## Candidate ranking and abstention

Selection occurs in two stages:

1. Decide among no expression, inline emoji, Discord reaction, or expressive media.
2. If emoji wins, rank eligible Unicode and guild candidates.

Signals include situation fit, semantic confidence, community evidence, placement suitability,
availability, recent positive feedback, and bounded relationship preference. Penalties include
recent repetition, family repetition, ambiguity, contradiction, sensitivity, low confidence, and
permission restrictions.

An emoji is eligible only when it exceeds both a minimum confidence threshold and the no-expression
candidate by a configured margin. Low-confidence custom emoji are observation-only. The selector
returns at most three candidates; the provider may still choose no emoji.

The style profile supplies the prior probability of any emoji. Situation fit may raise or lower that
probability, but ordinary casual chat inherits the human server baseline. Per-person emoji rate can
only move the server prior within a bounded range and requires enough observations.

## Natural-style ledger

The style ledger stores bounded fingerprints for recent assistant replies per channel and globally:

- inline Unicode and custom emoji
- Discord reactions
- emoji semantic families
- em dashes, spaced dashes, ellipses, repeated punctuation, and excessive lowercase openings
- normalized opening phrase
- sentence-length and clause-count buckets
- lightweight lexical shingles for repeated phrasing
- structured intent and response shape

Default repetition policy:

- exact emoji and semantic-family reuse are penalized relative to measured human reuse, not banned
- conspicuous punctuation is discouraged when its measured server rate is low
- repeated openings and highly similar phrases are penalized within the recent assistant window
- repeated joke or flirt shape is penalized within the same short conversation window

Cooldowns never rewrite quoted material, code, URLs, user names, or factual punctuation. A strong
semantic match may override a cooldown, and the override is recorded for evaluation.

## Generation and validation flow

```text
conversation context
  -> situation assessment
  -> catalog eligibility and style-ledger penalties
  -> expression guidance
  -> existing structured generation
  -> output validation
  -> Discord action execution
  -> style-ledger observation and feedback learning
```

Output validation checks that custom emoji IDs exist, are available, are permitted in the guild, and
were eligible for the turn. An invalid emoji is removed without discarding otherwise valid reply
text. Execution failures remain truthful in the turn trace.

## Operator controls

Configuration exposes conservative controls:

- enable or disable the skill
- enable guild emoji profiling
- minimum usage observations and confidence thresholds
- global emoji frequency target
- private-scope learning policy
- local visual model selection and resource limit

The operator interface supports inspecting, correcting, locking, disabling, and re-profiling custom
emoji meanings. Corrections outrank learned evidence and survive subsequent learning jobs.

## Failure handling

- Missing vision model: use names and usage evidence; keep visual confidence absent.
- Asset download or decode failure: retain prior profile and retry with bounded backoff.
- Missing archive: continue live observation without historical bootstrapping.
- Database migration failure: skill remains disabled; conversation generation continues unchanged.
- Unknown or deleted emoji: preserve history but exclude it from selection.
- Provider ignores guidance: validator removes ineligible custom emoji and records the deviation.
- Empty candidate set: return no-expression guidance.

The skill must fail open to an ordinary text response, never fail the conversation turn.

## Evaluation

### Unit tests

- Discord name changes preserve identity and learned meaning.
- Animated frame sampling is bounded and deterministic.
- Low-confidence profiles cannot become output candidates.
- Role-restricted, unavailable, deleted, or cross-guild emoji are rejected.
- Exact and semantic-family cooldowns decay at the specified boundaries.
- Strong contextual evidence can override a cooldown and records why.
- Em dashes in URLs, quotes, and code do not count as style habits.
- Private observations cannot alter guild-wide profiles.
- Operator corrections remain authoritative.
- Archive cursor updates are idempotent and process only new observations.

### Replay evaluation

The private production replay suite compares baseline and candidate behavior on held-out turns. It
measures:

- inline emoji rate
- exact and family repetition within rolling windows
- em-dash and repeated-opening frequency
- inappropriate emoji rate
- abstention rate
- valid custom emoji selection
- response-length and participation regressions
- distance from human message-length, sentence-count, emoji, punctuation, and casing distributions
- bounded person adaptation without phrase copying
- human preference on naturalness, appropriateness, and personality consistency

Initial rollout gates:

- candidate emoji rate within two percentage points of the held-out human rate
- candidate em-dash rate no more than 0.5 percentage points above the held-out human rate
- candidate multi-sentence rate within five percentage points of the held-out human rate
- candidate median word count within two words of the held-out human median
- repeated emoji and openings no higher than the held-out human rate
- zero invalid or inaccessible custom emoji emitted
- no statistically meaningful regression in participation or factual-answer fixtures
- human reviewers prefer the candidate on naturalness without rating it less contextually suitable

### Production rollout

1. Build profiles and ledger in shadow mode without changing replies.
2. Inspect custom emoji descriptions and confidence distributions.
3. Run private replay evaluation and correct systematic errors.
4. Enable guidance for a small channel allowlist.
5. Compare trace metrics and explicit feedback for one week.
6. Expand only after rollout gates hold.

Every decision records situation, candidates, penalties, abstention margin, selected placement, and
profile versions in the existing bounded turn trace. Raw private messages and emoji image bytes are
not copied into traces.

## Research basis

- Discord Emoji Resource: object identity, availability, animation, permissions, formats, CDN WebP,
  and deleted reaction-name behavior: <https://docs.discord.com/developers/resources/emoji>
- OpenAI CLIP: zero-shot text-image matching and its limitations:
  <https://openai.com/index/clip/>
- Barbieri et al., distributional emoji semantics from surrounding words:
  <https://aclanthology.org/L16-1626/>
- Barbieri et al., interpretable label-wise emoji prediction:
  <https://aclanthology.org/D18-1508/>
- Reelfs et al., interpretable word-emoji embeddings from messaging data:
  <https://aclanthology.org/2022.emoji-1.1/>
- Wu et al., multimodal emoji prediction from text and visual content:
  <https://aclanthology.org/N18-2107/>
- Kralj Novak et al., temporal variation in emoji semantics:
  <https://arxiv.org/abs/1805.00731>
- Welleck et al., repetition and unlikelihood training:
  <https://arxiv.org/abs/1908.04319>
- Holtzman et al., decoding strategy and repetitive text degeneration:
  <https://arxiv.org/abs/1904.09751>

## Decisions deferred to implementation planning

- Exact local vision-text model, subject to server CPU, memory, license, and measured profiling time.
- Database table and migration names, while preserving the contracts above.
- Exact scoring coefficients, to be calibrated from the shadow-mode and replay datasets rather than
  hard-coded from intuition.
