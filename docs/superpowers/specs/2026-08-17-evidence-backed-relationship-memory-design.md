# Evidence-Backed Relationship Memory Design

## Purpose

Mika should develop durable, person-specific familiarity from repeated conversations without
confusing inference with fact, copying one person's behavior onto another, or flooding every reply
with irrelevant history. The system must improve recall, continuity, correction handling, and
situation awareness while preserving Mika's own identity.

This design combines compatible ideas from `titanwings/colleague-skill` and
`MemTensor/memmy-agent`, both MIT-licensed. OpenViking's AGPL-licensed main project is used only as
an architectural reference. No AGPL implementation code, prompt text, or tests may be copied into
Mika.

## Current State and Gaps

Mika currently has:

- a recent per-channel message window;
- explicit user facts keyed by Discord user ID;
- bounded lexical recall over same-user and same-channel messages;
- optional Honcho semantic recall;
- aggregate reaction feedback;
- one global weekly reflection;
- aggregate human style profiles learned from the durable Discord archive.

The current system does not maintain an evidence-backed model of each relationship. It cannot
reliably distinguish explicit statements from inferred patterns, retain contradictions over time,
adopt corrections as first-class evidence, explain why a memory was recalled, or consolidate noisy
observations into a stable profile. Lexical overlap also misses paraphrases when Honcho is disabled.

## Design Principles

1. Mika remains one person. Relationship profiles change context and familiarity, not identity.
2. Explicit statements and corrections outrank behavioral inference.
3. A single message cannot establish a durable behavioral pattern.
4. Every derived memory remains traceable to source message IDs without duplicating raw archive
   content.
5. Retrieval is selective, scoped, token-budgeted, and observable.
6. Ambiguous classifications fail toward recent conversational continuity, not topic resets.
7. Memory extraction and consolidation never block a visible Discord reply.
8. All local memory behavior works without an external vector service or second generative model.
9. Optional semantic components must degrade to lexical retrieval without losing stored data.
10. Private-channel evidence never becomes guild-wide social knowledge.

## Relationship Profile

Each Discord user receives one versioned relationship profile scoped to the installation. Guild and
channel identifiers remain attached to evidence so retrieval can enforce visibility boundaries.

The profile contains six independent layers inspired by `colleague-skill`:

### Core relational posture

- current familiarity level;
- preferred degree of directness;
- stable interaction boundaries;
- how Mika should acknowledge uncertainty about the person.

### Expression DNA

- measured message length and casing;
- vocabulary and recurring phrases that are safe to recognize but not mechanically imitate;
- humor, emoji, punctuation, and response-rhythm tendencies;
- confidence and sample count for every aggregate.

Expression evidence guides conversational fit. It must not instruct Mika to impersonate the user or
repeat private phrases verbatim.

### Interests and shared context

- explicit preferences and dislikes;
- recurring topics;
- projects, games, media, people, or places the user repeatedly discusses;
- shared references between Mika and the user.

### Emotional and care patterns

- signals correlated with openness, discomfort, excitement, or withdrawal;
- ways the user explicitly says they prefer support;
- care signals Mika has used successfully according to direct feedback.

Emotional state is never stored as a diagnosis. Inferences use neutral, observable descriptions.

### Conflict and repair

- direct corrections the user made to Mika;
- communication preferences during disagreement;
- boundaries and rejected approaches;
- repair approaches explicitly accepted or repeatedly followed by positive feedback.

### Memory anchors

- short descriptions of important shared moments;
- stable references to source messages;
- dates and participants needed to disambiguate the event.

Memory anchors are summaries, not transcripts. Raw messages remain in the existing archive and
conversation tables.

## Evidence Model

Every relationship claim is represented independently from the rendered profile:

- `claim_id`;
- `subject_user_id`;
- `guild_id` and `channel_id` visibility scope;
- `kind` and normalized `key`;
- compact `value`;
- evidence class: `explicit`, `correction`, `repeated_behavior`, `reaction`, or `inference`;
- confidence in `[0, 1]`;
- supporting message IDs and observation count;
- first-observed, last-observed, and last-confirmed timestamps;
- lifecycle state: `candidate`, `active`, `disputed`, `superseded`, or `expired`;
- optional predecessor claim for corrections and revisions.

Activation rules are deterministic:

- explicit user statements may activate immediately at high confidence;
- direct corrections activate immediately and supersede the affected claim;
- repeated behavior requires at least three observations across at least two distinct days;
- reaction-derived preferences require at least three consistent signals and no strong negative
  signal;
- model inference begins as a candidate and requires corroboration before prompt injection;
- sensitive claims are never inferred from behavior.

Contradictory evidence does not overwrite history. It marks the old claim disputed or superseded,
links the replacement, and retains both source trails.

## Turn Relation Classifier

Before retrieval, a lightweight classifier determines how the incoming message relates to the
current conversation:

- `follow_up`;
- `correction`;
- `new_topic`;
- `topic_end`;
- `social_check_in`;
- `memory_probe`.

The first stage uses deterministic lexical, timing, reply-reference, and entity-overlap signals.
Short or referential messages default to `follow_up`. High-confidence corrections and topic endings
are handled without a model.

An optional small local classifier arbitrates only ambiguous cases. It consumes the previous user
message, previous Mika reply, new message, and structural Discord signals. It returns a closed label,
confidence, and short reason under a strict timeout. Timeout, invalid output, or unavailable model
falls back to the deterministic decision. It never generates the visible response.

The initial release provides the interface, deterministic classifier, shadow-mode measurements, and
an operator switch. A local model is enabled only after the benchmark proves an accuracy gain large
enough to justify its latency and memory footprint.

## Tiered Memory Representations

Memory uses three representations, independently implemented from the general concept of tiered
context:

- **Index:** one sentence, capped at 40 tokens, used for lexical or embedding candidate search.
- **Overview:** a compact structured profile or event summary, capped at 350 tokens, used for
  reranking and prompt injection.
- **Evidence:** source message references and bounded excerpts, loaded only for direct memory probes,
  corrections, or low-confidence conflicts.

The database stores index and overview text alongside their schema and generator versions. Evidence
continues to reference the canonical local message/archive record.

## Retrieval Pipeline

Retrieval operates in explicit stages:

1. Determine relation and required memory types.
2. Apply user, guild, channel, and privacy scope before scoring.
3. Collect exact facts, active relationship claims, recent messages, and historical candidates.
4. Score lexical overlap, optional semantic similarity, person affinity, channel affinity, recency,
   evidence confidence, and correction priority.
5. Apply diversity filtering so near-duplicates cannot consume the result set.
6. Reject candidates below the minimum score.
7. Render selected overviews within a strict token budget.
8. Record a privacy-safe recall trace.

The default score is deterministic and inspectable. Optional embeddings add one bounded signal; they
never replace scope, evidence confidence, or correction priority. Honcho remains an optional external
source and is merged after local retrieval with ID and text deduplication.

Recall traces record query hash, relation label, candidate IDs, selected IDs, rejection reasons,
estimated token cost, latency, and retrieval version. They do not duplicate message content.

## Extraction and Consolidation

Visible replies persist first. A bounded background observation job then considers the completed
turn for candidate evidence. Extraction processes only messages not previously observed, using a
durable cursor based on timestamp plus message ID.

Deterministic extractors handle measurable expression features, explicit correction phrases,
reaction feedback, and known fact forms. A provider-backed structured extractor may propose richer
claims, but those begin as `candidate` evidence and must obey the same activation rules.

A weekly consolidation job runs separately per person:

- groups claims by normalized key and semantic similarity when available;
- merges duplicate support without inflating confidence for repeated copies of one message;
- promotes sufficiently corroborated candidates;
- preserves temporal contradictions;
- decays unsupported behavioral inferences;
- expires stale low-confidence claims;
- rebuilds the compact relationship overview;
- writes a new immutable profile version only when content changes.

The previous versions remain available for rollback. A failed extraction or consolidation transaction
leaves the last active profile untouched and retries with bounded backoff.

## Correction Flow

Messages classified as corrections receive special handling. The system extracts the scene, the
incorrect assumption or behavior, and the requested replacement. When the target is ambiguous, Mika
responds normally and the claim remains a candidate rather than guessing.

A confirmed correction:

- creates a high-confidence correction claim;
- supersedes matching inferred or repeated-behavior claims;
- updates the relationship overview;
- influences the current turn when extraction completes before generation;
- remains visible in the audit history;
- can itself be superseded by a later correction.

Corrections never rewrite raw messages or silently erase prior evidence.

## Privacy and Controls

The operator can disable all relationship learning, semantic retrieval, provider-backed extraction,
or the optional local relation model independently. Per-user deletion removes derived claims,
profiles, embeddings, and recall traces while preserving server archives according to their separate
retention policy.

Direct-message evidence is scoped to that person and DM context. Private-channel evidence cannot be
used in public channels unless it represents an explicit, non-sensitive user fact marked as globally
usable. Other users' profiles are never injected merely because they share a channel.

The dashboard and CLI show counts, versions, last consolidation time, failure status, and source IDs.
They do not display private message text in aggregate operational views.

## Licensing and Attribution

Adapted MIT implementation or prompt fragments from `titanwings/colleague-skill` and
`MemTensor/memmy-agent` must be recorded in `THIRD_PARTY_NOTICES.md` with their copyright and MIT
license notices. Adaptation should favor Mika-native typed Python interfaces rather than mechanical
translation.

OpenViking main-project source is AGPL-3.0. Mika must not copy, translate, or create line-by-line
derivatives of that code unless the project owner explicitly chooses AGPL compliance for the combined
work. Architectural concepts are implemented independently against this specification and Mika's
existing interfaces. OpenViking components explicitly carrying Apache-2.0 may be evaluated
separately, with their notices, if a concrete component becomes necessary.

## Failure Handling

- Classifier failure: use deterministic `follow_up`-biased result.
- Embedding failure: use lexical and structured retrieval.
- Provider extraction failure: retain raw conversation and retry; do not create claims.
- Consolidation failure: keep the prior active profile version.
- Missing source message: exclude the evidence-dependent claim from prompt injection.
- Token-budget overflow: retain higher-confidence corrections and facts first, then relationship
  overviews, then historical messages.
- Database failure: fail open to recent conversation context and continue the visible turn.

## Evaluation

Unit and integration tests cover scoping, activation thresholds, contradiction preservation,
correction precedence, version rollback, cursor idempotency, timeout fallbacks, token budgeting,
deduplication, and deletion.

The memory benchmark uses held-out conversations and measures:

- explicit fact recall precision and recall;
- correct-person attribution;
- follow-up and correction classification accuracy;
- correction adoption on the next applicable turn;
- contradiction preservation;
- irrelevant-memory rejection;
- private-scope leakage, which must remain zero;
- duplicate injection rate;
- retrieval latency and prompt-token overhead;
- conversational quality relative to the current production baseline.

The benchmark compares lexical-only, local hybrid, and local-plus-Honcho configurations. Semantic or
model-assisted stages ship enabled only when they improve held-out accuracy without violating the
latency and leakage gates.

## Rollout

1. Add storage, deterministic relation classification, evidence ingestion, and recall traces in
   shadow mode.
2. Backfill candidate evidence from the durable archive without activating inferred claims.
3. Run the held-out benchmark and inspect person attribution and privacy failures.
4. Enable active explicit facts and corrections.
5. Enable corroborated relationship overviews and hybrid retrieval.
6. Enable weekly consolidation after profile diffs remain stable for one full cycle.
7. Evaluate the optional local classifier and embeddings independently before enabling either.

Deployment remains reversible through feature switches. Existing local memory and Honcho continue to
operate throughout migration.
