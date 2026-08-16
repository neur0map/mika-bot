# MikaV2 conversation-engine redesign

## Objective

Turn Mika from a request-driven assistant into a selective Discord participant whose
timing, memory, media understanding, tool use, reactions, and short-form voice feel
coherent across real conversations. At the same time, replace the current high-coupling
layout with independently testable domains and observable turn stages.

## Evidence and constraints

- Production local memory currently contains 734 messages from 11 users in six channels.
  Exact and lexical retrieval remain cheap at this scale.
- `LLMClient` currently owns memory assembly, prompt construction, routing, generation,
  repair, parsing, media gating, length limiting, and persistence.
- `bot/events/message.py` currently owns Discord scope, media extraction, model invocation,
  action execution, policy application, and archive telemetry.
- Tool use is selected with regular expressions before the provider sees the turn.
- Media context does not resolve the social meaning of replied-to or forwarded messages as
  one conversation unit.
- The dashboard shows configuration and health but not why a turn replied, stayed silent,
  reacted, searched, or failed to send media.
- Python remains the only product runtime. The official Bot API remains the only shipped
  Discord integration. No raw private conversations enter version control.
- The configured subscription-backed provider remains primary; the existing
  OpenAI-compatible provider remains fallback.
- Files stay below 500 lines, target 300 lines, and comments explain only non-obvious why.

## Source-backed decisions

- Discord message objects expose attachments, embeds, stickers, reactions, resolved reply
  messages, and forwarded snapshots separately. The ingress adapter must normalize all of
  them into one typed conversation envelope rather than treating media as an attachment
  list. See [Discord Message Resource](https://docs.discord.com/developers/resources/message).
- Current model guidance recommends lean prompts, exposing only task-relevant tools, and
  benchmarking representative tasks rather than assuming more instructions or effort are
  better. See [OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model).
- Current models accept image inputs, so visual evidence should remain native image input
  rather than being reduced to captions before generation. See
  [OpenAI model catalog](https://developers.openai.com/api/docs/models).
- Dense retrieval is most useful as a candidate generator followed by reranking. At Mika's
  present scale, SQLite recency, lexical relevance, user affinity, and exact scoring are
  simpler and fully inspectable. An embedding adapter can be added behind the same
  interface after recall evaluation justifies it. See
  [Sentence Transformers retrieve and rerank](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html).
- A PostgreSQL vector index is deferred. It is an operational option for a later corpus that
  needs approximate search, not a prerequisite for hundreds of messages. See
  [pgvector](https://github.com/pgvector/pgvector).

## Approaches considered

### 1. Prompt-only repair

Keep the current pipeline and expand the persona prompt with more examples and stronger
instructions. This is low effort, but it leaves regex routing, media-reference loss, mixed
responsibilities, and opaque failures intact. More prompt text also conflicts with the
source guidance to keep policy lean and evaluate changes independently.

### 2. Separate local classifier and vector service

Run every message through a trained intent model and store all memory in a vector database.
This can reduce main-provider calls at large scale, but the current corpus is too small and
weakly labeled for a trustworthy classifier. It also creates deployment and debugging
burden before retrieval quality has been measured.

### 3. Feature-first staged engine

Normalize Discord input, resolve conversational context, perform a cheap deterministic
eligibility pass, ask a narrow planner for semantic participation and tools, retrieve only
relevant memory, generate the visible turn, then execute and record actions. Each stage has
a typed input/output, trace record, focused tests, and one operator-facing diagnostic view.
This is the selected approach.

## Target package structure

```text
src/mika/
  core/                         process config, paths, logging, errors
  persistence/                  database engine and migrations only
    conversations/              message, turn-trace, and user-profile repositories
    settings/                   operator setting repository

  conversation/                platform-neutral member behavior
    contracts/                  envelopes, plans, turns, traces, errors
    context/                    thread assembly and reference resolution
    participation/              eligibility signals and semantic planner
    personality/                persona loading, user affinity, style constraints
    retrieval/                  recent, lexical, profile, and optional embedding recall
    perception/                 image/GIF evidence and durable media semantics
    generation/                 prompt assembly, provider call, repair, parsing
    actions/                    reaction and media action policies
    evaluation/                 blind cases, rubrics, runner, reports

  providers/                    external intelligence adapters
    primary_chat/               primary ACP process and image transport
    compatible_chat/            fallback HTTP chat adapter
    embeddings/                 optional local embedding adapter

  tools/                        model-callable capabilities
    web_search/                 schema, executor, result reducer
    media_search/               GIF/sticker/clip schema and executor
    registry/                   task-scoped tool exposure

  discord/                      official Bot API adapter
    ingress/                    message normalization and scope filtering
    context/                    reply, forward, embed, sticker, attachment resolution
    execution/                  typing, reply, reaction, and media sending
    events/                     thin event registration only

  abilities/                    optional slash-command abilities
    <ability_name>/              one folder with registration, handler, and tests contract

  web/                          operator HTTP interface
    routes/                     one resource per module
    diagnostics/                trace and benchmark read models
  cli/                          operator command interface
  system/                       service-process integration
```

Every package receives a concise `README.md` stating purpose, public interfaces, allowed
dependencies, and failure behavior. Compatibility imports remain temporarily at old paths
during migration, then are deleted after all callers move.

## Turn data flow

1. Discord ingress creates a `ConversationEnvelope` containing current text, author,
   channel, mentions, attachments, embeds, stickers, reply target, forward snapshots,
   recent reactions, and timestamps.
2. Context resolution follows the reply target and snapshot once, preserving who posted
   the original media and any accompanying text. A text reply to somebody else's GIF thus
   carries both the reply and the GIF as one unit.
3. Perception turns visual inputs into `MediaEvidence`. Static images remain native images.
   Animated GIFs produce a bounded three-frame contact sheet so motion/reaction changes are
   visible even when a provider inspects only one frame. A semantic summary produced during
   the normal turn is stored for later replies; it is never shown as an unsolicited caption.
4. Eligibility rules reject bots, DMs, disallowed guilds, unsupported system messages, and
   explicit cooldown violations. They do not decide social intent.
5. A narrow `ParticipationPlanner` sees recent human dialogue, references, media evidence,
   user relationship facts, and available tool summaries. It returns `ignore`, `observe`,
   `react`, or `engage`, plus intent, confidence, requested tools, and action appetite.
6. Retrieval combines same-user facts, same-channel recent context, lexical matches, and
   feedback-weighted examples. It returns bounded, attributed memories. Optional embeddings
   implement the same protocol and can be evaluated without changing generation.
7. Tool planning exposes only capabilities requested by the participation plan. Current-fact
   questions expose web search. Social opportunities may expose media search even without an
   explicit request. No regex alone can permanently disable tools.
8. Generation receives the persona, compact context, tool results, native media evidence,
   and a small action contract. It produces a `VisibleTurn` with optional text, one reaction,
   and one media action.
9. Action policy applies per-channel and per-user repetition budgets, but it never converts
   a deliberate silence into a generic assistant failure message.
10. Discord execution records attempted and visible actions. One `TurnTrace` stores stage
    decisions, latencies, retrieval identifiers, tool outcomes, parsing state, and suppression
    reasons without exposing secrets in the dashboard.

## Personality and participation

Mika's identity is stable; user relationships are contextual rather than separate personas.
The system stores bounded user facts, preferred tone, recurring topics, recent callbacks,
and reaction feedback. It never infers protected traits or creates dependency cues.

The planner distinguishes direct address from social invitation. A direct factual question
normally engages. Ambient human-to-human talk normally observes. A punchline, escalating bit,
shared media, callback, or room-wide prompt can invite a reaction or short contribution even
without a mention. Silence is a valid outcome and must be measured alongside over-participation.

Visible text defaults to one sentence. Emoji are ordinary punctuation, not a quota. Reactions
and GIFs are independent actions with cooldown and diversity budgets. Proactive media is
allowed only for high-confidence joke, hype, flirt, sarcasm, celebration, or reaction moments,
and the query derives from the conversational beat rather than a generic keyword.

## Memory and learning

The canonical store remains local and inspectable. New tables add normalized turn traces,
message relationships, media evidence, user facts, and feedback signals. An import job can
backfill the existing 734-message corpus without changing original rows.

Retrieval initially uses:

- same-channel recency;
- same-user affinity;
- SQLite FTS lexical relevance;
- explicit reply/thread relationship;
- positive/negative feedback weight;
- diversity limits so one old exchange cannot dominate context.

Reflection proposes user facts or general lessons with provenance and confidence. Facts expire
or are replaced when contradicted. Raw conversation is never committed. Training exports are
opt-in, anonymized, and separate from runtime retrieval.

## Tool and media behavior

Each tool lives in its own folder with a typed schema, eligibility function, executor, reducer,
timeouts, observability fields, and tests. The planner selects tools semantically; deterministic
checks only enforce availability, permission, and safety.

Media search becomes a first-class tool rather than a post-generation patch. The media result
includes provider, asset type, canonical URL, preview metadata, and failure reason. The response
composer can choose media-only, reaction-only, text-only, or a restrained combination. Failed
media lookup does not silently claim that media was sent.

## Operator frontend and diagnostics

The dashboard separates configuration from behavior evidence:

- Overview: runtime health, provider, message throughput, action rates, fallback rate.
- Conversation traces: stage timeline for a redacted turn, with participation, retrieval,
  tools, generation, policy, and execution decisions.
- Personality: persona source, active relationship-memory counts, recent approved lessons.
- Tools: availability, latency, success/failure totals, and last safe error.
- Media: inbound perception and outbound search/send rates.
- Evaluation: baseline/current benchmark score, category breakdown, regressions, latency.

The frontend consumes read models from `web/diagnostics`; it never reaches into Discord or
provider modules.

## Blind evaluation

The benchmark has three layers:

1. Deterministic contracts validate parsing, eligibility, reference resolution, media frame
   sampling, retrieval filtering, tool exposure, cooldowns, and trace completeness.
2. A committed synthetic social suite covers direct chat, ambient chatter, callbacks, teasing,
   flirting, criticism, comfort, current facts, image replies, GIF replies, proactive reaction,
   proactive media, and deliberate silence.
3. A private replay suite is generated from production history into `var/evaluation/`. It
   anonymizes IDs and replaces identifying literals while preserving conversational structure.

The model under evaluation receives an ordinary `ConversationEnvelope`; no prompt contains
benchmark, test, score, rubric, expected intent, or expected action. A separate deterministic
scorer and optional judge evaluate the transcript after generation. Baseline and candidate run
the identical cases with isolated memory namespaces. Reports include quality, participation
precision/recall, unsolicited-action rate, media-context correctness, tool correctness, style
length, repetition, latency, parse fallback, and action failures.

Initial acceptance gates:

- 100% deterministic contract pass rate;
- no regression in direct-answer correctness;
- at least 20% relative improvement in the combined social rubric over baseline;
- proactive reaction/media opportunities improve without exceeding 10% false-positive actions;
- referenced-media cases use the media as context in at least 90% of scored cases;
- structured fallback below 2%;
- visible action failure below 2%;
- median normal-turn latency reported and no more than 25% worse without a documented quality win.

## Migration sequence

1. Add contracts, trace storage, and blind baseline runner around existing behavior.
2. Extract Discord ingress/context/execution with compatibility imports.
3. Extract provider, tool, parser, and generation adapters.
4. Add participation planning and task-scoped tool exposure.
5. Add referenced-media perception and durable media semantics.
6. Add hybrid retrieval, user facts, and history backfill.
7. Move optional command abilities into one-folder units or remove those outside the agreed
   conversation-member product boundary.
8. Add dashboard diagnostics and benchmark views.
9. Remove compatibility paths after callers and tests migrate.
10. Run blind baseline/candidate comparisons, iterate on measured failures, and deploy behind
    reversible feature flags.

## Error handling and rollback

Each stage returns typed failures that the trace records. Perception failure retains textual
context. Retrieval failure degrades to recent history. Tool failure returns no fabricated facts
or assets. Primary-provider failure uses the configured fallback. Parse failure can retry once
with the same evidence. Discord execution failure records the rejected action.

Feature flags independently select the legacy or new planner, retrieval, perception, and action
executor. Database migrations are additive until benchmark and production rollout gates pass.

## Completion evidence

Completion requires the target directories and README contracts, no oversized orchestration
files, all old callers migrated, full static/test gates, blind benchmark reports showing the
acceptance thresholds, dashboard trace visibility, a production-path container run, and a
limited real-channel rollout with archived visible-action evidence.
