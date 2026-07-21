# Mika conversation-only companion implementation plan

> **For Hermes:** Use `subagent-driven-development` task-by-task. Never deploy/start the bot until the applicable pre-flight gate passes.

**Goal:** Convert MikaV2 into a conversation-only Discord companion that is concise, socially selective, reliable with structured actions, and capable of well-timed reactions/GIFs without filling the server with bot noise.

**Architecture:** Keep Discord event code thin. The LLM service produces a strict typed `mika_turn.v2` decision (`reply`, reaction, media, or silence); a deterministic policy layer validates/limits it; the Discord event executor performs the selected action and archives outcome telemetry. Current-fact tools are isolated from normal social turns. A provider capability layer makes strict schemas available without forcing every provider into OpenAI-specific behavior.

**Tech stack:** Python 3.12, discord.py, Pydantic, AsyncOpenAI-compatible providers, SQLite/shared archive, pytest, Ruff, mypy, Docker Compose.

**Baseline:** Latest observed quality is 52/100. Do not credit `af8df01` with behavioral improvements until a new live cohort exists.

**Global rules:**

- Mika stays stopped through build/test phases.
- Never commit raw Discord content, tokens, database files, logs, or secrets.
- Every behavior task follows red → green → `make check` → commit.
- Every commit must remain conventional, human-authored, and contain no attribution trailers.
- Before any Discord API mutation or bot start, create a VPS source/config backup and record a rollback target.

---

## Phase 0 — establish measurements and a safe test cohort

### Task 0.1: Add a privacy-safe behavior metrics report

**Objective:** Make pre/post rollout quality measurable without committing raw conversations.

**Files:**
- Create: `tools/report_turn_metrics.py`
- Create: `tests/test_report_turn_metrics.py`
- Modify: `dev_docs/MIKAV2-IMPROVEMENT-NOTES.md`

**Steps:**
1. Write failing fixture tests that feed anonymized event dictionaries and assert counts for `parseStatus`, reply-length buckets, `brain snagged`, silence, reactions, selected media, sent media, inbound media, and action-on-inbound-media.
2. Implement a read-only report command that accepts a SQLite path and date bounds and emits JSON/Markdown aggregate metrics only.
3. Run `uv run pytest tests/test_report_turn_metrics.py -v` until green.
4. Run `make check`.
5. Commit:
   ```bash
   git commit -m "feat(metrics): report conversation quality aggregates"
   ```

**Gate:** The report must not output raw message content, author IDs, URLs with query secrets, or database rows.

### Task 0.2: Build a versioned conversation evaluation fixture set

**Objective:** Turn observed failures into deterministic regressions before changing model/provider behavior.

**Files:**
- Create: `tests/fixtures/conversation_turns.json`
- Create: `tests/test_conversation_evals.py`
- Modify: `tests/test_client.py`
- Modify: `tests/test_message_media_context.py`

**Fixtures must cover:**
- unmentioned human-to-human banter → `silence`
- direct factual question → concise text and optional tool route
- joke/roast → one short reply or reaction, no web search
- incoming GIF with no explicit question → reaction, short social reply, matching GIF, or silence; never a caption
- explicit GIF request → Klipy media action
- plain question with stray media choice → media suppression
- malformed provider output → bounded repair/fallback telemetry
- reply length over social cap → clean shortening

**Steps:** red fixture tests, minimum implementation hooks, focused tests, full gate, then commit:
```bash
git commit -m "test(chat): add conversation quality fixtures"
```

**Gate:** Fixtures remain synthetic/anonymized. No copied Discord conversations are committed.

---

## Phase 1 — remove the command product safely

### Task 1.1: Add conversation-only runtime tests before removal

**Objective:** Protect the message path while command code is deleted.

**Files:**
- Create: `tests/test_message_event_integration.py`
- Modify: `tests/test_smoke.py`
- Retain: `tests/test_message_media_context.py`, `tests/test_media_helpers.py`, `tests/test_social_turn_contracts.py`

**Test cases:**
- Mention and allowed free-chat channel each invoke one LLM turn.
- DMs and out-of-scope guild/channel messages do not invoke the LLM.
- Reaction-only and media-only actions do not post empty text.
- `silence` posts nothing but records decision telemetry.
- Klipy failure leaves a text/reaction turn intact.

**Steps:** implement fake Discord message/channel fixtures; red tests; preserve existing behavior; full gate; commit:
```bash
git commit -m "test(bot): cover conversation event execution"
```

### Task 1.2: Remove slash-command registration and source package

**Objective:** Remove every application-command runtime path while keeping the existing `commands.Bot` event lifecycle initially.

**Files:**
- Delete: `src/mika/bot/commands/` (all feature modules, `__init__.py`, helpers, README)
- Modify: `src/mika/bot/client.py`
- Modify: `src/mika/core/config.py`
- Modify: `src/mika/bot/events/ready.py`
- Modify: `src/mika/bot/__init__.py`
- Modify: `pyproject.toml`
- Modify: `.env.example`

**Implementation requirements:**
- Remove `register_all`, command tree sync, and `commands_enabled` settings/branches.
- Keep `commands.Bot` only as an implementation shell until message-event integration tests prove that a future `discord.Client` migration is safe.
- Change presence from `/help` to a conversation-oriented activity or remove it.
- Keep `src/mika/bot/media.py`; it is required by normal chat GIF/sticker/clip actions.
- Remove command-only dependencies only after import audit proves no retained code needs them.

**Steps:** write a failing test that app startup has no command registration; remove code; run `uv run pytest tests/test_message_event_integration.py -v`; run `make check`; commit:
```bash
git commit -m "refactor(bot): remove slash command runtime"
```

### Task 1.3: Remove stale Discord commands through a staged migration

**Objective:** Delete commands already registered with Discord; code removal alone is insufficient.

**Files:**
- Create: `src/mika/cli/commands/cleanup_commands.py`
- Create: `tests/test_cleanup_commands.py`
- Modify: `src/mika/cli/app.py`
- Create: `docs/COMMAND-CLEANUP.md`

**Implementation requirements:**
- Provide an explicit, operator-only command requiring a `--confirm` argument.
- Enumerate global and configured-guild application commands, display planned deletion counts, then use Discord's bulk overwrite API with an empty command list.
- Archive only counts/timestamps, never tokens or command payloads with user data.
- Do not run this against production until a test application/guild run proves API/UI count zero.

**Gate:** Carlos explicitly approves the production cleanup after test-guild validation. This is an external visible deletion, so it is not automatic.

**Commit:**
```bash
git commit -m "feat(cli): add staged command cleanup"
```

### Task 1.4: Remove non-chat server automation and command harness

**Objective:** Make the shipped Discord behavior strictly conversational.

**Files:**
- Delete: `src/mika/bot/events/antispam.py`, `src/mika/bot/antispam.py`
- Delete: `src/mika/bot/events/members.py`, `src/mika/bot/greetings.py`
- Modify: `src/mika/bot/events/__init__.py`
- Delete: `dev-testing/harness.py`, command-category test files and command-only `conftest.py`
- Preserve/migrate: reflection state currently using generic guild configuration; do not delete `GuildConfig` or `repositories/config.py` until reflection state is moved or proven retained.

**Gate:** Weekly reflection read/write test passes after each persistence change.

**Commit:**
```bash
git commit -m "refactor(bot): remove non-chat guild automation"
```

### Task 1.5: Rewrite product/operator documentation

**Objective:** Remove all framework, command, ticket, moderation, fun, and `/help` claims.

**Files:**
- Modify: `README.md`, `ARCHITECTURE.md`, `AGENTS.md`, `docs/GETTING-STARTED.md`, `docs/DISCORD-SETUP.md`, `docs/COSTS.md`, `docs/UPDATING.md`, `docs/DASHBOARD.md`, `packaging/README.release.md`
- Modify: `src/mika/web/routes/overview.py`, `src/mika/web/templates/overview.html`
- Delete/rewrite: command screenshots and `src/mika/bot/components/`, `features/` placeholder READMEs
- Optional strict-scope removal: `userbot/` and its CLI registration, only after separate confirmation that personal userbot tooling should leave this repository.

**Requirements:** Dashboard reports conversation health: selected model, provider capability mode, memory/reflection state, allowed guild/channel scope, media availability, and latest aggregate quality metrics—not command totals.

**Commit:**
```bash
git commit -m "docs: position Mika as conversation-only"
```

---

## Phase 2 — make structured social decisions reliable

### Task 2.1: Introduce a provider capability contract

**Objective:** Express whether a provider supports JSON object mode, strict JSON Schema, image input, and tools instead of assuming OpenAI behavior.

**Files:**
- Modify: `src/mika/ai/llm/providers/base.py`
- Modify: `src/mika/ai/llm/providers/openai_compatible.py`
- Create: `src/mika/ai/llm/providers/capabilities.py`
- Create: `tests/test_provider_capabilities.py`

**Implementation requirements:**
- Add typed capabilities and a typed response-format object; do not widen to untyped `Any` at call sites.
- Map OpenAI strict `json_schema` response format when supported.
- Preserve `json_object` and current parser/retry fallback for gateways/local servers that cannot enforce schemas.
- Keep tools disabled for ordinary social turns; current-fact routes may use a tool loop and need a separate schema-safe finalization path.

**Tests:** strict-schema request construction, JSON-object fallback construction, tool-finalization schema request, unsupported-provider graceful degradation.

**Commit:**
```bash
git commit -m "feat(llm): add structured output capabilities"
```

### Task 2.2: Make `mika_turn.v2` a strict Pydantic/JSON Schema contract

**Objective:** Eliminate most parser fallbacks and make invalid action combinations impossible at the model boundary.

**Files:**
- Modify: `src/mika/ai/llm/turn.py`
- Modify: `src/mika/ai/llm/client.py`
- Create: `tests/test_turn_schema.py`

**Contract rules:**
- Closed intent/media/reaction enums.
- `silence` requires empty reply, no reactions, no media.
- A media action requires a non-empty normalized query.
- Reaction-only and media-only turns remain legal.
- A normal social turn must be short by contract/policy, not only prompt text.
- Record parse outcome as `strict_json`, `json_repaired`, `plain_fallback`, or `provider_error`.

**Gate:** Existing fixtures plus 100 generated malformed payload tests must pass; strict-schema capable providers must produce zero malformed payloads in a fixed smoke suite.

**Commit:**
```bash
git commit -m "feat(llm): enforce Mika turn schema"
```

### Task 2.3: Build the provider benchmark harness

**Objective:** Select models based on Mika's actual conversation contract, not generic benchmarks.

**Files:**
- Create: `tools/run_conversation_benchmark.py`
- Create: `tests/test_conversation_benchmark.py`
- Create: `dev_docs/MODEL-BENCHMARKS.md`

**Benchmark matrix:**
- Candidates: current MiniMax route, GPT-5.4 mini, Claude Opus 4.8 route, Qwen3.6 local experimental route.
- Run the same synthetic fixtures with tools disabled/enabled as appropriate.
- Measure: schema pass rate, median/p95 latency, reply length, policy violations, correct silence/action selection, reaction/GIF decision precision, tool call correctness, and cost estimate.
- Store aggregate/censored results only; never commit raw Discord prompts.

**Decision gate:** GPT-5.4 mini becomes default only if it achieves at least 98% schema success, p95 social-turn latency acceptable for the VPS, and no regression in fixture score. Opus is premium/A-B until it provides a measurable social-judgment win. Qwen remains experimental until local tool/JSON smoke tests pass.

**Commit:**
```bash
git commit -m "test(llm): benchmark conversation providers"
```

---

## Phase 3 — make Mika feel socially alive, not merely valid

### Task 3.1: Add explicit interaction context and a deterministic action policy

**Objective:** Separate “what Mika says” from “whether Mika should act.”

**Files:**
- Create: `src/mika/ai/llm/social_policy.py`
- Modify: `src/mika/ai/llm/client.py`
- Modify: `src/mika/bot/events/message.py`
- Create: `tests/test_social_policy.py`

**Inputs:** mention/free-channel status, direct-question signal, reply-chain signal, inbound media kind/count, last Mika action time, recent action mix, current conversation state.

**Rules:**
- Direct mentions/questions must receive an answer unless a provider failure is recorded.
- Unmentioned free-channel messages may select silence.
- Do not use GIFs/reactions on a fixed quota; require a model suggestion plus policy eligibility.
- Add channel-level cooldowns for outbound media and repeated reactions to avoid spam.
- Preserve action-only behavior.

**Tests:** social cooldown, direct-question override, no response to unrelated chatter, incoming media action eligibility, no repeated media spam.

**Commit:**
```bash
git commit -m "feat(chat): add social action policy"
```

### Task 3.2: Treat inbound media as an input, not a filename

**Objective:** Stop captioning unknown GIFs and let Mika respond to media with appropriate social judgment.

**Files:**
- Create: `src/mika/ai/llm/media_context.py`
- Modify: `src/mika/bot/events/message.py`
- Modify: `src/mika/ai/llm/client.py`
- Create: `tests/test_media_turn_policy.py`

**Implementation:**
- Preserve MIME type, source, title, and social context for every attachment/embed.
- For supported configured providers, use image input on image attachments and a sampled/thumbnail image for GIF/video only when safely downloadable and under explicit byte/time limits.
- If visual analysis is unavailable, label uncertainty; never infer a GIF's contents from a filename as fact.
- For media-only messages, prioritize reaction/short reply/matching GIF/silence. Never produce a descriptive caption without a user question.

**Gate:** All attachment fetches must be bounded by allowlist, content-type, byte cap, timeout, and safe failure behavior. No media bytes are persisted unless existing archive policy explicitly permits it.

**Commit:**
```bash
git commit -m "feat(media): add social media understanding"
```

### Task 3.3: Instrument action execution, not just model intent

**Objective:** Distinguish “model chose GIF” from “Klipy found it” and “Discord posted it.”

**Files:**
- Modify: `src/mika/bot/events/message.py`
- Modify: `src/mika/bot/media.py`
- Modify: `src/mika/shared_archive.py` or archive event writer
- Create: `tests/test_media_execution_telemetry.py`

**Telemetry fields:** selected action, policy suppression reason, Klipy attempt/result/error class, Discord post result/error class, action latency, media cooldown state, final visible outcome.

**Commit:**
```bash
git commit -m "feat(metrics): trace social action outcomes"
```

---

## Phase 4 — make learning real and controlled

### Task 4.1: Make reflection explicit, observable, and reversible

**Objective:** Replace dormant reflection plumbing with an auditable weekly learning loop.

**Files:**
- Modify: `src/mika/ai/learning/reflection/__init__.py`
- Create: `src/mika/ai/learning/reflection/quality.py`
- Modify: `src/mika/bot/scheduler.py`
- Modify: `src/mika/persistence/...` only after locating the exact reflection state model
- Create: `tests/test_reflection_quality.py`

**Requirements:**
- Reflection is disabled by default until configured deliberately.
- It consumes aggregate outcomes and selectively sampled, privacy-safe recent context according to existing retention rules.
- It writes dated, bounded lessons with provenance/metrics and expires superseded lessons.
- It must not rewrite the persona, invent relationship facts, or turn a single reaction into a permanent preference.

**Gate:** Unit tests show a reflection can be stored, injected, superseded, and disabled. Dashboard/CLI shows last-run time and lesson count without displaying private source messages.

**Commit:**
```bash
git commit -m "feat(learning): add auditable reflection loop"
```

### Task 4.2: Link feedback to Mika-authored outcomes

**Objective:** Learn from reactions to Mika, not ambient reactions between humans.

**Files:**
- Modify: `src/mika/bot/events/reactions.py`
- Modify: archive/persistence event writer
- Create: `tests/test_reply_feedback_linking.py`

**Requirements:**
- Resolve reaction target author before classifying feedback.
- Record only feedback tied to Mika's sent message/action.
- Track non-response and media-action outcomes separately.
- Do not optimize against raw reaction volume; a quiet, appropriate answer is sometimes correct.

**Commit:**
```bash
git commit -m "feat(learning): link feedback to Mika replies"
```

---

## Phase 5 — staged rollout and proof

### Task 5.1: Build and smoke-test without Discord login

**Steps:**
1. Run `make check`.
2. Build the Docker image while Mika remains stopped.
3. Run provider/turn fixture smoke tests in an ephemeral container with Discord token access disabled.
4. Run the aggregate metrics report against the pre-rollout archive and save only its aggregate output in deployment notes.
5. Create a VPS backup of source/config before any live change.

**Gate:** 100% deterministic tests green; strict-schema provider smoke suite passes; no configuration secret appears in output.

### Task 5.2: Controlled live cohort

**Steps:**
1. Start Mika only in a test guild or one explicitly chosen low-traffic channel.
2. Collect at least 100 eligible turns and at least 15 inbound-media opportunities before evaluating GIF/reactive behavior.
3. Compare with the 52/100 baseline using the metrics report.
4. Stop/rollback if structured fallback exceeds 5%, `brain snagged` appears, action failures exceed 2%, or user-visible spam/incorrect media is reported.

**Success targets:**
- ≥98% valid structured turns for strict-schema provider route.
- Social reply median ≤80 characters; p95 ≤180 except marked explanatory intents.
- Zero valid-silence turns rendered as failure text.
- Inbound-media behavior manually evaluated from sufficient sample size; no quota-based GIF target.
- Reflection state has a dated successful run only after feedback links are proven.

### Task 5.3: Full rollout and postmortem

**Steps:**
1. Promote the selected provider route only after cohort gate passes.
2. Resume watchdog only when the bot is intentionally live.
3. Archive aggregate before/after metrics and release notes.
4. Commit deployment documentation:
   ```bash
   git commit -m "docs: record conversation rollout results"
   ```

**Rollback:** stop/recreate prior image and restore the timestamped VPS source/config backup; do not delete archive data.

---

## Recommended immediate order

1. Commit this plan and research report.
2. Implement Phase 0 and Task 1.1 before deleting commands.
3. Complete Phase 1 with Discord command cleanup staged separately from source deletion.
4. Complete Phase 2 before any model switch; choose the provider with Mika-specific benchmark evidence.
5. Implement Phase 3 media/action policy, then Phase 4 learning.
6. Start only a controlled cohort and score it before full rollout.
