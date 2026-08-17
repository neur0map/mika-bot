# Source-Port Audit: Evidence-Backed Relationship Memory

**Audit date:** 2026-08-17
**Scope:** Implemented code and tests only in `titanwings/colleague-skill`,
`MemTensor/memmy-agent`, and `volcengine/OpenViking`, compared with Mika's
approved design and implementation plan. Roadmaps, product claims, and prompt
text were not treated as implementation evidence. Source navigation used
`prowl-agent overview`, `search`, `outline`, `def`, and `peek` against all
three repositories.

## Decision summary

Mika's approved design already covers the essential source-derived architecture:
per-person layers, evidence classes and activation thresholds, correction
supersession, immutable profile versions, tiered scoped retrieval, background
work, deletion, privacy-safe recall traces, and a held-out benchmark. Do not
port any OpenViking source or prompt text. The additions below are small
Mika-native requirements that materially improve safety, auditability, or recall
quality without expanding the product into a general memory platform.

| Decision | Mechanism missed by the plan | Add to |
|---|---|---|
| Add now | Associate explicit feedback with the exact recall event and selected claims; retain outcome statistics separately from claim truth. | Tasks 2, 4, 6, 8 |
| Add now | Budget context breadth-first, then deepen only with remaining budget; fall back to a lower tier instead of truncating an entry. | Task 4 |
| Add now | Reject lossy consolidation that drops active correction or explicit-fact anchors unless the claim was intentionally superseded/expired; salvage genuinely new entries. | Task 5 |
| Add now | Version relationship-memory policy/settings and record the effective version in observations and recall traces. | Tasks 2, 6, 7 |
| Add now | Add content-free, operation-scoped telemetry for extraction, consolidation, and retrieval stages. | Tasks 6, 7, 8 |
| Add now | Pin a versioned benchmark-case manifest and persist per-mode, per-case artifacts, not only aggregate JSON. | Task 8 |

## Licensing gate

| Repository | Evidence | License status | Mika decision |
|---|---|---|---|
| `colleague-skill` | `colleague-skill/LICENSE:1-21` | MIT; copyright 2026 titanwings. | Direct adaptation is permitted only with the required copyright and MIT notice. The approved plan's `THIRD_PARTY_NOTICES.md` requirement is sufficient. |
| `memmy-agent` | `memmy-agent/LICENSE:1-21` | MIT; copyright 2026-present MemTensor. | Direct adaptation is permitted only with the required copyright and MIT notice. The plan already requires that notice. |
| `OpenViking` | `OpenViking/LICENSE:1-80`; main modules declare `SPDX-License-Identifier: AGPL-3.0`, e.g. `OpenViking/openviking/telemetry/operation.py:1-3`. | AGPL-3.0. | Do **not** copy, translate, or derive from source, prompts, or tests. The mechanisms below are independently stated requirements, not a port. |

## Implemented mechanisms compared with Mika

### `colleague-skill` (MIT)

| Implemented mechanism and exact source | Mika coverage | Decision |
|---|---|---|
| Relationship persona is explicitly layered into relational rules, expression DNA, emotional logic, conflict/repair, and memory signature in `prompts/relationship/persona_builder.md:1-122`. The analyzer separates evidence from inference and marks insufficient material in `prompts/relationship/persona_analyzer.md:1-108`. | Covered and safer: the specification keeps equivalent independent layers, source IDs, confidence, and activation rules. | **Intentionally exclude direct port.** The source is a skill-generation workflow, not runtime memory; its example replies and signature phrases conflict with Mika's no-impersonation requirement. The layer taxonomy is already captured in the approved spec. |
| `backup_current_artifacts` and `update_skill` archive the old artifact set before mutation and regenerate a versioned profile (`tools/skill_writer.py:253-389`); `apply_correction` appends an explicit scene/wrong/correct record (`tools/skill_writer.py:302-322`). Tests prove archived version and correction-count behavior (`tests/test_skill_writer.py:264-343`). | Covered: immutable profile versions, correction claims, predecessors, audit history, and rollback are requirements; Tasks 2 and 5 implement them. | **Intentionally exclude direct port.** No additional plan work: Mika's normalized claims are stronger than a Markdown correction log. Retain the useful acceptance tests conceptually: a correction must remain inspectable after a later profile version exists. |

### `memmy-agent` (MIT)

| Implemented mechanism and exact source | Mika coverage | Decision |
|---|---|---|
| Retrieval derives query/time intent, gathers candidates, filters/reranks, applies a hard context budget, and records candidate, selected, and dropped IDs (`Memory/src/service/retrieval/retrieval-service.ts:1519-1608`). Optional LLM filtering has bounded timeouts, validates output, and falls back deterministically with a structured warning (`Memory/src/service/retrieval/retrieval-service.ts:1839-2012`). | Covered: Mika specifies deterministic scoring, optional semantic signal, budgeted rendering, IDs/rejection reasons, and local fallback. | **Intentionally exclude query-rewrite/LLM-filter port.** It violates the first-release local/no-second-model focus and is unnecessary before Mika's deterministic benchmark establishes a gap. Preserve the existing deterministic fallback guarantee. |
| Recall events retain candidate/injected/dropped sets (`Memory/src/storage/repositories.ts:177-206`, `:1905-1984`); `applyRecallOutcome` updates per-memory positive/negative/ignored recall statistics through the feedback service (`Memory/src/service/feedback/feedback-experience.ts:1349-1416`, `:1680-1750`). | Mika records a recall trace but the plan has no explicit linkage from a direct user reaction/correction to that trace or its selected claims. | **Add now.** Add `recall_feedback` records keyed by recall event, feedback source, and outcome. Keep truth/confidence immutable: feedback affects only a separately thresholded ranking-quality signal, and a direct correction still creates the normal correction claim. Test duplicate feedback idempotency, no feedback-to-claim-truth mutation, and candidate attribution. |
| Explicit feedback is classified into correction/preference/constraint repair guidance, with direct correction receiving higher confidence (`repairIssueFromFeedback` and prompt construction in `Memory/src/service/feedback/feedback-experience.ts:1785-1872`; exercised in `Memory/tests/service/feedback/decision-repair.test.ts:404-471`). | Mika has correction extraction but not an explicit structured channel for non-correction preference/constraint feedback about recalled context. | **Add now, narrowly.** Reuse Mika's `EvidenceProposal`/claim kinds for explicit preferences and boundaries; add a feedback-attribution interface rather than Memmy's general decision-repair system. Do not generate procedural "repair skills." |
| Reflection scoring persists `usable`, `alpha`, reason, source, and scoring time alongside the generated summary (`updateTraceReflection`, `Memory/src/service/evolution/span-pipeline.ts:752-822`), and its worker writes an auditable before/after change (`:128-235`). | Mika uses deterministic activation and candidate state; provider proposals are candidates. | **Intentionally exclude a second LLM quality scorer now.** Add only schema validation/normalization reasons to the deterministic extractor's trace. A second model adds cost and failure modes before the first benchmark justifies it. |
| Privacy lifecycle is implemented and tested as raw-text redaction, archive/delete status, and audit logs (`Memory/tests/service/lifecycle/memory-lifecycle.test.ts:121-169`); sensitive secrets are redacted before storage/logging by `redactSensitiveText` (`Memory/src/utils/sensitive-data.ts:1-33`). `MemoryRow.visibility` has explicit private/public/session values (`Memory/src/types.ts:99-150`). | Mika already forbids trace content duplication, scopes evidence before scoring, and separates derived-memory deletion from archive retention. | **Intentionally exclude raw-archive redaction/deletion port.** Mika's archive has its own retention policy by design. Add no new raw-content copying. Keep the planned deletion test strict for derived claims/profiles/embeddings/traces and consider archive-redaction only as a separate archive-retention project. |

### `OpenViking` (AGPL-3.0; architecture only)

| Implemented mechanism and exact source | Mika coverage | Decision |
|---|---|---|
| The context assembler chooses a tier, substitutes a lower-detail form when the normal tier is unavailable/too expensive, and never deepens a resource merely to compensate for a missing abstract (`openviking/retrieve/context_assembler/tiers.py:106-226`). Its budgeter first places each candidate at a base tier, then spends remaining budget on depth upgrades; it caps individual entries, deduplicates rendered bodies, and does not truncate oversized entries (`openviking/retrieve/context_assembler/budget.py:1-180`). | Mika specifies index/overview/evidence, a strict budget, and diversity filtering but not the breadth-before-depth allocation rule or non-truncating downgrade rule. | **Add now.** In Task 4, render corrections/explicit facts first, then give each remaining eligible claim one cheapest safe representation before spending leftover budget on higher-ranked overview/evidence. Set a per-entry token cap; downgrade or reject rather than slice evidence into misleading fragments. Record `budget_cap`, selected tier, and downgrade reason in the trace. |
| Consolidation guard rejects an UPDATE that loses too many bullets or lexical anchors, then salvages genuinely new items; it also throttles oversized growth (`Session._wm_enforce_key_facts_consolidation`, `openviking/session/session.py:4819-5005`). | Mika preserves contradictions and produces an immutable version only when content changes, but it does not require a guard against a syntactically valid yet lossy overview rewrite. | **Add now.** In Task 5, validate a proposed profile against its active predecessor: active correction IDs and active explicit-fact IDs must remain rendered unless the exact claim is superseded, disputed, or expired. Reject an invalid rebuild, retain the old profile, and optionally salvage only new validated entries. Test this separately from database rollback. |
| Session commit uses durable Phase-1 markers and tracks completed memory extraction steps to avoid replay (`Session._write_phase1_marker`, `_ensure_phase1_ready`, and `commit_async`, `openviking/session/session.py:1571-1778`, `:2499-2618`); integration tests cover phase-two concurrency (`tests/session/test_session_retention_integration.py:1545-1591`). | Mika's source ID dedupe, timestamp/message-ID cursor, and idempotent retry tests cover the required relationship-memory scope. | **Intentionally exclude the two-phase archive protocol.** Mika does not own its Discord archive transaction. Strengthen the existing Task 6 test wording to require stage-specific idempotency (`observed`, `activated`, `profile-versioned`) but do not introduce a second archive/queue system. |
| Privacy configs have immutable version snapshots with updater, timestamp, and change reason (`UserPrivacyConfigMeta`/`UserPrivacyConfigVersion`, `openviking/privacy/models.py:1-84`), with current/version/list/activate API flow (`openviking/server/routers/privacy_configs.py:41-153`). | Mika provides independent operator switches but neither spec nor plan requires a stable settings/policy version in observation or recall audit data. | **Add now.** Model a small immutable `relationship_memory_policy_version` (effective switches plus scope rules; no secrets), record it on observation, profile version, and recall trace, and show it in CLI/dashboard metadata. This makes a privacy decision reproducible after settings change. |
| Operation-scoped telemetry supports counters, gauges, duration measurements, per-stage token usage, structured errors, and one final snapshot (`OperationTelemetry`, `openviking/telemetry/operation.py:453-750`); `run_with_telemetry` attaches the requested safe payload (`openviking/telemetry/execution.py:27-222`). | Mika has per-recall traces and dashboard counts, but no explicit aggregate/phase telemetry for extraction, consolidation, retries, fallback, or p95 measurement. | **Add now.** Add content-free operation metrics for `relationship.observe`, `relationship.retrieve`, and `relationship.consolidate`: outcome, phase durations, candidate/selected/rejected counts, retry/fallback reason, profile change/no-op, and estimated tokens. Hash IDs where needed; never include query/message/profile text. Use the metrics as Task 8's p95 source. |
| LoCoMo runners preserve per-question IDs, evidence references, category, question time, and outputs for later judging (`benchmark/locomo/openviking/run_eval.py:1-220`, `:884-975`); statistics are reported by category (`benchmark/locomo/openviking/stat_judge_result.py:67-260`). | Mika's Task 8 lists metrics and modes but does not explicitly require a frozen fixture manifest, case IDs, or per-case output artifact. | **Add now.** Keep Mika's relationship-specific held-out corpus—do not import OpenViking's benchmark code/data/prompt. Add a versioned manifest containing scenario ID, privacy class, expected claim IDs/labels, and mode; persist per-case safe results and aggregate by relation/privacy/correction category. This makes benchmark regressions diagnosable and comparable. |

## Exact plan amendments

1. **Task 2:** Extend `record_recall` with `policy_version`; add idempotent
   `record_recall_feedback(recall_event_id, feedback_id, outcome, claim_ids)` and
   a separate claim-ranking-feedback projection. Do not change claim evidence
   class, state, or confidence from a recall outcome.
2. **Task 4:** Add tests for breadth-first allocation, per-entry cap,
   downgrade-not-truncate behavior, and feedback quality as a bounded ranking
   feature. The existing scope check must still happen before every score.
3. **Task 5:** Add a predecessor-preservation validation test: a rebuilt
   overview which silently drops an unsuperseded correction/explicit fact is
   rejected while a newly corroborated claim may still be promoted.
4. **Task 6:** Persist the effective policy version at the beginning of an
   observation/recall operation; emit safe stage timings and fallback/retry
   counters. Require stage-specific idempotency in addition to cursor
   idempotency.
5. **Task 7:** Expose active policy version and operation-health aggregates,
   without raw text or unhashed query data.
6. **Task 8:** Add a checked-in benchmark manifest and per-case JSONL results;
   aggregate by relation class, correction behavior, retrieval mode, and privacy
   class. Retain the current zero-leakage hard gate and performance thresholds.

## Explicit non-adoptions

- No prompt, test, implementation, or translation from OpenViking (AGPL-3.0).
- No generic autonomous skill/decision-repair system from Memmy; Mika needs
  relationship claims, not reusable agent procedures.
- No second LLM solely to judge extraction/reflection quality in the initial
  release; deterministic validation plus the existing candidate thresholds are
  adequate until the benchmark shows a need.
- No raw Discord archive redaction/deletion behavior as part of this feature;
  derived-memory deletion remains complete, while archive retention is governed
  separately as the approved specification requires.
- No phrase/example-reply imitation from colleague-skill; preserve Mika's own
  identity and avoid replaying private language verbatim.

## Approved-spec and plan amendment (2026-08-17)

The approved design and implementation plan now incorporate all five recommended safeguards:

- idempotent feedback-to-recall/selected-claim linkage that never mutates claim truth;
- breadth-first tier budgeting with per-entry caps and downgrade-not-truncate rendering;
- predecessor validation that rejects consolidation dropping active corrections or explicit facts;
- immutable effective privacy/operator policy versions recorded on observations, profiles, and recalls;
- content-free stage telemetry plus stable-manifest, per-case safe benchmark artifacts.

The amendments preserve the already committed integration clarifications in `5241160` and retain the
AGPL non-adoption boundary.
