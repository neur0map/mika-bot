# Natural Expression Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stateful, context-aware expression skill that understands Unicode and guild emoji, prefers abstention, prevents repetitive emoji and punctuation habits, and proves improvement with a deterministic benchmark.

**Architecture:** A pure conversation-layer skill produces compact expression guidance from recent history, a semantic emoji catalog, and a bounded style ledger. The LLM client injects this guidance before structured generation, then validates returned text/reactions against the same decision. Discord guild synchronization supplies custom emoji profiles without coupling the core selector to Discord objects.

**Tech Stack:** Python 3.12, dataclasses, regex, SQLAlchemy models, discord.py, pytest, existing conversation benchmark tooling.

## Global Constraints

- No second generative intent model in this version.
- No raw private-message duplication in emoji profiles or traces.
- Custom emoji identity is its Discord snowflake, never its mutable name.
- The no-expression candidate is the default and must beat no-expression by a confidence margin.
- Cooldowns are penalties with explicit contextual overrides, never global punctuation bans.
- The skill fails open to an ordinary text response.
- Every implementation task follows red-green-refactor and ends in a focused commit.

---

### Task 1: Expression contracts, Unicode semantics, and situation assessment

**Files:**
- Create: `src/mika/conversation/skills/README.md`
- Create: `src/mika/conversation/skills/__init__.py`
- Create: `src/mika/conversation/skills/natural_expression/README.md`
- Create: `src/mika/conversation/skills/natural_expression/__init__.py`
- Create: `src/mika/conversation/skills/natural_expression/contracts.py`
- Create: `src/mika/conversation/skills/natural_expression/unicode_catalog.py`
- Create: `src/mika/conversation/skills/natural_expression/situation.py`
- Test: `tests/conversation/skills/natural_expression/test_situation.py`

**Interfaces:**
- Produces: `SocialSituation`, `EmojiProfile`, `ExpressionCandidate`, `ExpressionGuidance`, `assess_situation(text: str, intent: str, confidence: float, mentioned: bool) -> SocialSituation`, and `unicode_candidates(situation: SocialSituation) -> tuple[EmojiProfile, ...]`.

- [ ] Write tests proving serious/low-confidence messages abstain, joke/hype/comfort map to distinct semantic families, and the Unicode catalog offers broad families without forcing a candidate.
- [ ] Run `uv run pytest tests/conversation/skills/natural_expression/test_situation.py -q` and verify collection fails because the package does not exist.
- [ ] Implement immutable contracts, conservative situation scoring, and curated semantic families covering amusement, warmth, support, hype, skepticism, awkwardness, sadness, agreement, curiosity, and celebration.
- [ ] Re-run the focused tests and commit with `feat(expression): add situation-aware emoji semantics`.

### Task 2: Style ledger and contextual selection

**Files:**
- Create: `src/mika/conversation/skills/natural_expression/style_ledger.py`
- Create: `src/mika/conversation/skills/natural_expression/selector.py`
- Create: `src/mika/conversation/skills/natural_expression/skill.py`
- Test: `tests/conversation/skills/natural_expression/test_style_ledger.py`
- Test: `tests/conversation/skills/natural_expression/test_selector.py`

**Interfaces:**
- Consumes: Task 1 contracts and Unicode profiles.
- Produces: `StyleLedger.observe(channel_id: str, reply: str, reactions: tuple[str, ...]) -> None`, `StyleLedger.snapshot(channel_id: str) -> StyleSnapshot`, `ExpressionSelector.select(...) -> ExpressionGuidance`, and `NaturalExpressionSkill.guide(...)` / `validate(...)`.

- [ ] Write failing tests for exact emoji cooldown, semantic-family cooldown, em-dash cooldown, repeated openings, quoted/code/URL exclusions, strong-context override, custom candidate ranking, and no-expression abstention.
- [ ] Run both focused test modules and verify expected missing-symbol failures.
- [ ] Implement bounded channel ledgers, Unicode grapheme extraction, punctuation/opening fingerprints, candidate scoring, and compact guidance rendering.
- [ ] Implement validation that removes recently repeated inline emoji and em-dash cadence only when the decision did not authorize an override; preserve quoted text, code, and URLs.
- [ ] Re-run focused tests and commit with `feat(expression): add contextual style cooldowns`.

### Task 3: Guild emoji profiles and persistence

**Files:**
- Create: `src/mika/conversation/skills/natural_expression/guild_catalog.py`
- Create: `src/mika/conversation/skills/natural_expression/visual_profile.py`
- Create: `src/mika/persistence/conversations/expression_models.py`
- Create: `src/mika/persistence/conversations/expression_profiles.py`
- Modify: `src/mika/persistence/models/__init__.py`
- Modify: `src/mika/bot/client.py`
- Test: `tests/conversation/skills/natural_expression/test_guild_catalog.py`
- Test: `tests/persistence/conversations/test_expression_profiles.py`

**Interfaces:**
- Produces: `GuildEmojiDescriptor`, `GuildEmojiCatalog.sync(guild_id: str, emoji: Iterable[GuildEmojiDescriptor])`, `VisualProfiler.describe(...)`, and `ExpressionProfileRepository` upsert/list/correct methods.

- [ ] Write failing tests proving snowflake identity survives renames, inaccessible/deleted/role-restricted emoji are ineligible, descriptions survive sync, animated metadata is preserved, and operator corrections remain locked.
- [ ] Run focused tests and verify expected failures.
- [ ] Implement additive profile/evidence tables, repository operations, pure guild catalog synchronization, and a pluggable visual-profiler protocol with deterministic name/usage fallback.
- [ ] Wire BotApp readiness and guild-emoji update events to synchronize visible emoji metadata without downloading assets on the event loop.
- [ ] Re-run focused tests and commit with `feat(expression): learn guild emoji profiles`.

### Task 4: Generation integration and execution feedback

**Files:**
- Modify: `src/mika/ai/llm/client.py`
- Modify: `src/mika/conversation/generation/prompt.py`
- Modify: `src/mika/conversation/actions/planner.py`
- Modify: `src/mika/conversation/engine.py`
- Test: `tests/test_prompt.py`
- Test: `tests/conversation/actions/test_planner.py`
- Test: `tests/conversation/test_engine.py`

**Interfaces:**
- Consumes: `NaturalExpressionSkill` from Task 2 and guild candidates from Task 3.
- Produces: generation advice appended to the current user turn and ledger updates only for successfully rendered output.

- [ ] Write failing integration tests showing recent emoji/em-dash fingerprints reach the prompt, unauthorized repeats are sanitized, reaction-only choices remain valid, and failed Discord sends do not advance cooldowns.
- [ ] Run focused integration tests and verify failures describe the missing integration.
- [ ] Inject compact guidance in both legacy `reply()` and staged `generate()` paths, validate parsed turns, and observe only successful execution in `ConversationEngine.observe()`.
- [ ] Re-run focused tests and commit with `feat(expression): integrate natural expression guidance`.

### Task 5: Benchmark, documentation, and release verification

**Files:**
- Create: `tests/fixtures/natural_expression_benchmark_v1.json`
- Create: `src/mika/conversation/evaluation/expression_benchmark.py`
- Create: `tools/run_natural_expression_benchmark.py`
- Test: `tests/conversation/evaluation/test_expression_benchmark.py`
- Modify: `src/mika/conversation/README.md`
- Modify: `dev_docs/MIKAV2-CHANGELOG.md`

**Interfaces:**
- Produces: deterministic baseline/candidate reports containing exact-repeat rate, family-repeat windows, adjacent em-dash cadence, abstention, invalid-custom-emoji count, and per-case failures.

- [ ] Write failing benchmark tests using held-out English/Spanish, joking, flirting, criticism, support, serious, media, Unicode, and custom-emoji cases derived from production patterns without copying private message text.
- [ ] Verify the benchmark test fails because scoring and runner are absent.
- [ ] Implement baseline and candidate evaluation, JSON output, threshold validation, and a CLI that exits nonzero when rollout gates fail.
- [ ] Run `uv run pytest tests/conversation/evaluation/test_expression_benchmark.py -q` and the benchmark CLI; save and inspect baseline/candidate metrics.
- [ ] Run `make check`, `git diff --check`, and the benchmark CLI again from the final tree.
- [ ] Update documentation with measured results and commit with `feat(expression): benchmark natural conversation style`.

