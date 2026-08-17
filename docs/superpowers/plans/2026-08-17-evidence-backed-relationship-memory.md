# Evidence-Backed Relationship Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build versioned, evidence-backed per-person relationship memory with correction precedence, tiered hybrid recall, durable consolidation, and measurable privacy-safe behavior.

**Architecture:** Typed conversation-layer components classify turn relations, extract evidence, rank scoped memories, and render bounded context. Persistence owns immutable claims, profile versions, observation cursors, and recall traces; optional semantic/model stages sit behind protocols and always degrade to deterministic local behavior.

**Tech Stack:** Python 3.12, SQLAlchemy async ORM, SQLite, existing provider interfaces, pytest, ruff, mypy.

## Global Constraints

- Mika remains one person; profiles change relationship context, not identity.
- Explicit statements and corrections outrank behavioral inference.
- Private-channel evidence never becomes guild-wide social knowledge.
- Visible replies must not wait for background extraction or consolidation.
- Local memory must work without Honcho, embeddings, or a second model.
- Persistence must not import `mika.conversation`; conversation services map domain objects to
  primitive persistence records.
- Claims and evidence carry visibility kind, guild/channel scope, source kind, source message ID,
  and source timestamp. Unresolved legacy facts are never prompt-injected.
- Copy/adapt MIT material only with notices; do not copy AGPL implementation or prompt text.
- New Python files stay under 300 lines where practical and never exceed 500 lines.
- Every behavior change follows a witnessed red-green test cycle.
- `make check` and the held-out memory benchmark must pass before deployment.

---

### Task 1: Relation classifier and shared contracts

**Files:**
- Create: `src/mika/conversation/relationships/contracts.py`
- Create: `src/mika/conversation/relationships/relation.py`
- Create: `src/mika/conversation/relationships/__init__.py`
- Create: `src/mika/conversation/relationships/README.md`
- Create: `tests/conversation/relationships/test_relation.py`
- Create: `THIRD_PARTY_NOTICES.md`

**Interfaces:**
- Produces `RelationKind`, `RelationDecision`, `EvidenceClass`, `ClaimState`, `MemoryLayer`, `RelationshipClaim`, and `classify_relation(...) -> RelationDecision`.
- The classifier accepts current text, previous user text, previous assistant text, elapsed seconds, and whether the message replies to an earlier message.

- [ ] **Step 1: Write failing behavioral tests** covering explicit correction, explicit topic end, referential follow-up, unrelated new topic, memory probe, and ambiguous short-message fallback. Assert closed labels, confidence ranges, and diagnostic signals.
- [ ] **Step 2: Run `uv run pytest tests/conversation/relationships/test_relation.py -q`** and verify failure because the package does not exist.
- [ ] **Step 3: Implement immutable contracts and deterministic classification.** Use correction phrases, topic-end phrases, memory-probe phrases, reply references, pronoun/reference signals, elapsed time, and token overlap. Default ambiguous cases to `follow_up`.
- [ ] **Step 4: Add MIT notices** for `titanwings/colleague-skill` and `MemTensor/memmy-agent`, identifying adapted relationship layers and turn-relation concepts.
- [ ] **Step 5: Run the focused test and `uv run mypy src/mika/conversation/relationships`.** Both must pass.
- [ ] **Step 6: Commit** with `feat(memory): classify conversational relations`.

### Task 2: Durable claims, profile versions, cursors, and recall traces

**Files:**
- Create: `src/mika/persistence/conversations/relationship_models.py`
- Create: `src/mika/persistence/conversations/relationship_memory.py`
- Create: `src/mika/persistence/conversations/relationship_records.py`
- Create: `src/mika/persistence/conversations/archive_reader.py`
- Modify: `src/mika/persistence/models/__init__.py`
- Modify: `src/mika/persistence/conversations/__init__.py`
- Create: `tests/persistence/conversations/test_relationship_memory.py`

**Interfaces:**
- Defines persistence-owned primitive DTOs: `ClaimWrite`, `ClaimRecord`, `EvidenceWrite`,
  `ProfileVersionRecord`, `ArchiveCursor`, `RecallEventWrite`, `RecallFeedbackWrite`,
  `RelationshipMemoryPolicyVersionRecord`, and `ArchiveSourceRecord`. Their values are primitives
  and persisted enum values are strings.
- `RelationshipMemoryRepository` accepts and returns only those DTOs; it must never import
  `mika.conversation`. `conversation/relationships/service.py` maps Task 1 domain contracts to and
  from the DTOs.
- Produces repository methods: `add_evidence`, `activate_claim`, `supersede_claim`,
  `claims_for_user`, `write_profile_version`, `active_profile`, `advance_cursor`, `cursor`,
  `record_recall`, `record_recall_feedback`, `write_policy_version`, `active_policy_version`,
  `delete_user_memory`, and `migrate_resolved_legacy_facts`.
- `ArchiveReader.iter_after(cursor: ArchiveCursor | None, limit: int)` opens the configured shared
  archive read-only and returns `ArchiveSourceRecord` values ordered strictly by
  `(archive_created_at, discord_message_id)`.

- [ ] **Step 1: Write failing repository and archive-reader tests** using the real temporary SQLite engine. Cover source deduplication, correction supersession, immutable profile and policy versions, compound archive cursor ordering `(archive_created_at, discord_message_id)`, read-only archive access, scoped claims, recall trace metadata, and complete derived-memory deletion. Add idempotent recall-feedback tests that link one feedback ID to one recall event and its selected claim IDs while proving that feedback cannot mutate claim value, evidence class, confidence, lifecycle state, or predecessor. Add migration cases that copy guild/channel/source visibility only when `conversation_user_facts.source_message_id` resolves to a valid archive source; assert unresolved legacy facts are excluded from relationship recall.
- [ ] **Step 2: Run the focused persistence test** and verify missing models/repository failure.
- [ ] **Step 3: Implement normalized ORM tables and primitive DTOs** for claims, claim evidence, profile versions, immutable relationship-memory policy versions, observation cursors, recall events, and recall-feedback-to-claim joins. Store visibility kind, guild ID, channel ID, source kind, source ID, and normalized source timestamp with every evidence row; store the effective policy version on observation, profile, and recall records; never copy transcripts. A ranking-feedback projection may aggregate only distinct feedback outcomes and may not update claim truth fields. Register every new ORM model through `persistence/models/__init__.py` so `init_db()` creates the tables.
- [ ] **Step 4: Implement the read-only archive adapter and transactional repository operations.** The adapter uses SQLite read-only mode, validates UTC timestamp plus Discord message ID before yielding a row, and never advances a cursor itself. Correction supersession and new profile activation must be atomic. Duplicate evidence for one source must not increase observation count.
- [ ] **Step 5: Run focused tests and `uv run mypy src/mika/persistence/conversations`.** Verify no persistence module imports `mika.conversation`; both checks must pass.
- [ ] **Step 6: Commit** with `feat(memory): persist relationship evidence`.

### Task 3: Evidence extraction and activation policy

**Files:**
- Create: `src/mika/conversation/relationships/extraction.py`
- Create: `src/mika/conversation/relationships/activation.py`
- Create: `tests/conversation/relationships/test_extraction.py`
- Create: `tests/conversation/relationships/test_activation.py`

**Interfaces:**
- Consumes relationship contracts and relation decisions.
- Produces `EvidenceProposal`, `extract_deterministic_evidence(...)`, and `ActivationPolicy.evaluate(claim, evidence) -> ActivationDecision`.

- [ ] **Step 1: Write failing tests** for explicit preferences, identity facts, direct corrections, measurable expression observations, non-sensitive boundaries, rejection of diagnoses/sensitive inference, and source-message traceability.
- [ ] **Step 2: Write failing policy tests** proving explicit facts and corrections activate immediately, behavior requires three observations over two days, reactions require three consistent signals, inference remains candidate, and corrections outrank all other evidence.
- [ ] **Step 3: Run both tests** and verify failures reference missing APIs.
- [ ] **Step 4: Implement conservative deterministic extractors.** Extract only closed, auditable patterns; normalize keys and cap values. Do not infer protected or medical attributes.
- [ ] **Step 5: Implement the activation policy** as a pure function with literal thresholds and reasons returned for tracing.
- [ ] **Step 6: Run focused tests and commit** with `feat(memory): extract relationship evidence`.

### Task 4: Tiered local hybrid retrieval

**Files:**
- Create: `src/mika/conversation/relationships/scoring.py`
- Create: `src/mika/conversation/relationships/rendering.py`
- Modify: `src/mika/conversation/context/retrieval.py`
- Modify: `src/mika/conversation/context/contracts.py`
- Create: `tests/conversation/relationships/test_scoring.py`
- Modify: `tests/conversation/context/test_retrieval.py`

**Interfaces:**
- Consumes active claims, profile overview, candidate messages, relation decision, and optional `SemanticScorer.score(query, documents) -> Sequence[float]`.
- Produces ranked `MemoryCandidate` values, bounded rendered context, selected/rejected IDs,
  selected tiers, rejection/downgrade reasons, latency, token estimates, and a bounded
  ranking-quality signal derived only from attributed recall feedback.

- [ ] **Step 1: Write failing scoring tests** for person and channel scope, correction priority, confidence, recency, lexical overlap, semantic contribution, duplicate diversity, deterministic lexical fallback, and a feedback ranking signal that remains zero until three distinct attributed outcomes exist and never overrides correction or evidence priority.
- [ ] **Step 2: Write failing retrieval integration tests** proving correct-person attribution, no DM-to-public leakage, legacy-unscoped-fact rejection, irrelevant rejection, Honcho-independent recall, breadth-first allocation after corrections/explicit facts, per-entry cap, and downgrade-not-truncate behavior.
- [ ] **Step 3: Run focused tests** and verify behavioral failures against the existing lexical retriever.
- [ ] **Step 4: Implement index/overview/evidence candidates** and an inspectable weighted scorer. Scope candidates before scoring and cap semantic influence.
- [ ] **Step 5: Implement bounded rendering** that prioritizes corrections and explicit facts, assigns every remaining eligible candidate its cheapest safe representation breadth-first, then deepens higher-ranked entries only with remaining budget. Enforce a per-entry cap and downgrade to a precomputed lower-detail representation or reject the entry rather than slicing it mid-entry. Record selected tier plus every drop/downgrade reason.
- [ ] **Step 6: Integrate with `AffinityRetriever`** while retaining its public protocol and fail-open behavior. When relationship retrieval is enabled, replace the existing unscoped `UserFact` prompt section with migrated scoped relationship claims; never merge legacy global facts as a fallback.
- [ ] **Step 7: Run focused tests and commit** with `feat(memory): add tiered hybrid relationship recall`.

### Task 5: Profile consolidation and rollback

**Files:**
- Create: `src/mika/conversation/relationships/consolidation.py`
- Create: `src/mika/conversation/relationships/profile.py`
- Create: `tests/conversation/relationships/test_consolidation.py`

**Interfaces:**
- Consumes claims and evidence grouped by subject.
- Produces `RelationshipProfile`, `ConsolidationResult`, and `RelationshipConsolidator.consolidate(...)` with deterministic merge, promotion, decay, contradiction preservation, and overview rendering.

- [ ] **Step 1: Write failing tests** for duplicate merging without confidence inflation, candidate promotion, temporal contradiction preservation, correction replacement, stale weak-inference expiry, stable no-op reruns, rollback-safe output, and predecessor preservation. The predecessor test must reject an otherwise valid overview that drops an active correction or active explicit fact unless that exact claim is superseded or expired, while permitting newly validated entries to be salvaged.
- [ ] **Step 2: Run the test** and verify missing consolidation APIs.
- [ ] **Step 3: Implement typed profile layers** for posture, expression, interests, care patterns, conflict/repair, and anchors. Every rendered entry carries claim IDs internally.
- [ ] **Step 4: Implement deterministic consolidation** using normalized keys, evidence precedence, observation diversity, and timestamps. Before activation, verify every active correction and explicit-fact claim remains represented from the predecessor unless that exact claim is superseded or expired; reject lossy output, retain the active profile, and salvage only newly validated entries. Produce a new version only when canonical content changes.
- [ ] **Step 5: Run focused tests and commit** with `feat(memory): consolidate relationship profiles`.

### Task 6: Runtime observation and background jobs

**Files:**
- Create: `src/mika/conversation/relationships/service.py`
- Create: `src/mika/conversation/relationships/telemetry.py`
- Create: `src/mika/ai/learning/reflection/relationship_job.py`
- Modify: `src/mika/conversation/engine.py`
- Modify: `src/mika/conversation/context/observer.py`
- Modify: `src/mika/bot/client.py`
- Modify: `src/mika/bot/scheduler.py`
- Modify: `src/mika/ai/llm/client.py`
- Modify: `src/mika/core/config.py`
- Create: `tests/conversation/relationships/test_service.py`
- Modify: `tests/conversation/test_engine.py`

**Interfaces:**
- Consumes repository, extractor, activation policy, classifier, retriever, and consolidator.
- Produces `RelationshipMemoryService.observe_turn`, `recall`, `consolidate_user`, and `run_pending_observations`.
- `ConversationEngine.observe` calls the service only after the executor has a visible success
  (reply, reaction, or media); local recent-history persistence retains its existing behavior.
- `BotApp` composes the service, `start_schedulers` starts the bounded job after Discord readiness,
  and `BotApp.close` cancels/awaits the job before shutdown.

- [ ] **Step 1: Write failing service tests** proving visible generation completes before observation, cursor retries and each `observed`/`activated`/`profile-versioned` stage are idempotent, failed extraction leaves the cursor unchanged, corrections can affect the next applicable turn, disabled learning performs no derived writes, and planned silence plus fully failed plans enqueue no relationship observation while reply-only, reaction-only, and media-only successes do. Assert observations and recalls store the effective immutable policy version.
- [ ] **Step 2: Write failing engine integration tests** proving relation and relationship overview reach generation while extraction failures fail open.
- [ ] **Step 3: Run focused tests** and verify failures against the current engine.
- [ ] **Step 4: Implement the orchestration service and lifecycle wiring** with dependency injection and bounded background batches. `ConversationEngine.observe` persists the existing local turn first, then submits relationship observation only after successful visible Discord execution. Wire `relationship_job.py` through `bot/scheduler.py`, retain its task/loop for shutdown, expose failures without advancing the cursor, and never block the visible action path. Emit one content-free operation record for observation, retrieval, and consolidation with outcome, phase durations, candidate/selected/rejected counts, estimated tokens, fallback/retry reason, profile changed/no-op status, effective policy version, and only hashed correlation IDs.
- [ ] **Step 5: Integrate recall into context selection and generation.** Merge local and Honcho context with deduplication; keep existing fallbacks.
- [ ] **Step 6: Add settings** for relationship learning, provider extraction, semantic scoring, shadow mode, batch size, and consolidation interval. Each effective switch/scope-rule change writes an immutable, content-free policy version with timestamp and change reason; no setting value may expose secrets.
- [ ] **Step 7: Run focused tests and commit** with `feat(memory): integrate relationship learning`.

### Task 7: Archive backfill, deletion, and operator visibility

**Files:**
- Create: `src/mika/cli/commands/relationship_memory.py`
- Modify: `src/mika/cli/app.py`
- Modify: `src/mika/web/routes/overview.py`
- Modify: `src/mika/web/settings_catalog.py`
- Create: `tests/cli/test_relationship_memory.py`
- Create: `tests/web/test_relationship_memory_overview.py`

**Interfaces:**
- Consumes `RelationshipMemoryService`, `ArchiveReader`, and a durable archive cursor.
- Produces CLI operations for status, bounded backfill, consolidate, inspect metadata, and delete-user-derived-memory; overview exposes counts and health without message text.

- [ ] **Step 1: Write failing CLI tests** for dry-run/status, resumable bounded backfill, strict continuation from `(archive_created_at, discord_message_id)`, deletion confirmation, archive-unavailable/degraded reporting, active policy version, operation-health aggregates, and no raw content or unhashed query data in status output.
- [ ] **Step 2: Write failing web tests** for claim/profile counts, active policy version, last consolidation, content-free operation-health aggregates, and degraded-state reporting without private text.
- [ ] **Step 3: Run focused tests** and verify missing command/fields.
- [ ] **Step 4: Implement commands and overview data** using service/repository APIs and the read-only archive adapter. Backfill creates candidates only; it never auto-activates inferred claims, never writes to the archive, and advances the named archive cursor only after the corresponding relationship transaction commits. Show the active policy version and aggregate operation health without raw content. Make the overview snapshot async before it queries aggregate relationship status.
- [ ] **Step 5: Run focused tests and commit** with `feat(memory): operate relationship memory`.

### Task 8: Held-out benchmark, documentation, and production rollout

**Files:**
- Create: `src/mika/conversation/evaluation/relationship_memory.py`
- Create: `tests/conversation/evaluation/test_relationship_memory_benchmark.py`
- Create: `tests/fixtures/relationship_memory_benchmark_v1.json`
- Create: `tools/run_relationship_memory_benchmark.py`
- Modify: `docs/HONCHO-MEMORY.md`
- Modify: `docs/GETTING-STARTED.md`
- Modify: `src/mika/conversation/README.md`
- Modify: `dev_docs/MIKAV2-CHANGELOG.md`

**Interfaces:**
- Produces a checked-in versioned benchmark manifest, deterministic cases, aggregate JSON results, and
  safe per-case JSONL artifacts for fact recall, attribution, relation accuracy, correction adoption,
  contradiction handling, irrelevant rejection, leakage, duplicates, latency, and prompt cost.
- Replays every held-out case turn chronologically through an isolated temporary relationship store with deterministic timestamps. Hidden expectations are available only to post-replay scoring, never to generation or retrieval.

- [ ] **Step 1: Write failing evaluator tests and a multi-turn fixture manifest** with literal expected metrics and thresholds, including a mandatory zero private-leakage gate. Every case has a stable ID, relation class, privacy class, expected claim IDs or labels, and supported retrieval modes. Include a correction whose replacement is tested on the next turn, a contradiction, a DM/public isolation pair, and archive-cursor continuation; assert that the responder never receives hidden expectations and that per-case artifacts contain only IDs, decisions, scores, timings, and metrics.
- [ ] **Step 2: Run the focused test** and verify missing evaluator failure.
- [ ] **Step 3: Implement stateful evaluator and CLI runner** supporting lexical-only, local-hybrid, and local-plus-Honcho modes without exposing expected answers to generation. Do not reuse the single-final-turn `evaluation.runner.run_cases` flow for relationship metrics; replay and observe each chronological turn before scoring the case. Emit safe JSONL per-case artifacts and aggregate results grouped by relation class, correction behavior, privacy class, and retrieval mode.
- [ ] **Step 4: Run the held-out benchmark** against the current baseline and candidate. Require no recall-quality regression, zero leakage, correction adoption at or above 95%, correct-person attribution at or above 98%, and p95 local retrieval below 100 ms.
- [ ] **Step 5: Run `make check`** and require all lint, format, type, and test gates to pass.
- [ ] **Step 6: Run `prowl-agent changed` and `prowl-agent doctor`** and inspect unresolved references and blast radius.
- [ ] **Step 7: Update documentation and changelog** with actual measured results and operator controls.
- [ ] **Step 8: Commit** with `feat(memory): benchmark relationship recall`.
- [ ] **Step 9: Push `main`, rebuild production, and verify** Discord connection, memory-service health, database integrity, new table availability, archive cursor progress, no startup errors, and zero container restarts.

## Plan Self-Review

- All specification sections map to Tasks 1 through 8.
- The runtime remains usable after every task; new behavior is enabled only during Task 6.
- OpenViking concepts are independently specified and implemented; only MIT sources permit direct adaptation.
- Types passed between tasks use stable names declared in each interface block.
- Every production behavior has a failing-test step before implementation.
- Privacy, attribution, rollback, and benchmark gates are explicit rather than implied.
- Persistence DTOs, archive source ordering, runtime scheduler wiring, legacy fact scope migration, and
  stateful benchmark replay are explicit before implementation.
- Recall-feedback attribution, breadth-first downgrade-safe rendering, consolidation predecessor
  preservation, immutable policy versions, content-free telemetry, and per-case benchmark artifacts
  are explicit before implementation.
