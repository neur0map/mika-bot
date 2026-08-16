# Context and evaluation foundation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the typed conversation envelope, referenced-media resolver, turn traces,
and blind benchmark foundation that make the larger MikaV2 redesign measurable.

**Architecture:** Platform-neutral contracts live under `conversation/contracts`.
Discord ingress adapts message objects into those contracts without invoking providers.
Additive repositories persist diagnostic traces. The evaluation runner invokes the ordinary
conversation boundary with hidden expectations that are never included in model input.

**Tech Stack:** Python 3.12, dataclasses, SQLAlchemy 2 async ORM, discord.py, FastAPI,
pytest, pytest-asyncio, SQLite.

## Global Constraints

- Python remains the only product runtime.
- The official Discord Bot API remains the only shipped Discord integration.
- The configured subscription-backed provider remains primary; the HTTP provider remains fallback.
- Raw private Discord conversations and secrets never enter version control.
- Public Python modules, classes, and functions are fully typed and briefly documented.
- Python files stay under 500 lines and target 300 lines.
- Comments explain only non-obvious constraints.
- Every created directory has a concise `README.md` describing purpose and dependencies.
- Production behavior changes use a failing test before implementation.

---

### Task 1: Conversation contracts

**Files:**
- Create: `src/mika/conversation/README.md`
- Create: `src/mika/conversation/__init__.py`
- Create: `src/mika/conversation/contracts/README.md`
- Create: `src/mika/conversation/contracts/__init__.py`
- Create: `src/mika/conversation/contracts/media.py`
- Create: `src/mika/conversation/contracts/envelope.py`
- Create: `src/mika/conversation/contracts/trace.py`
- Test: `tests/conversation/contracts/test_envelope.py`

**Interfaces:**
- Produces: `MediaAsset(kind, url, filename, content_type, source, width, height)`.
- Produces: `ReferencedMessage(message_id, author_id, author_name, text, media)`.
- Produces: `ConversationEnvelope(message_id, channel_id, guild_id, author_id,
  author_name, text, mentioned, created_at, media, referenced)`.
- Produces: `StageTrace(stage, outcome, reason, duration_ms, details)` and
  `TurnTrace(trace_id, message_id, channel_id, stages)`.

- [ ] **Step 1: Write contract tests**

```python
def test_envelope_visual_inputs_include_current_and_referenced_media() -> None:
    current = MediaAsset(kind="image", url="https://cdn/current.png", source="attachment")
    previous = MediaAsset(kind="gif", url="https://cdn/reaction.gif", source="embed")
    envelope = ConversationEnvelope(
        message_id="2",
        channel_id="10",
        guild_id="20",
        author_id="30",
        author_name="carlos",
        text="this is literally you",
        mentioned=False,
        created_at=datetime(2026, 8, 16, tzinfo=UTC),
        media=(current,),
        referenced=ReferencedMessage("1", "40", "alice", "", (previous,)),
    )

    assert envelope.visual_inputs == (current, previous)
```

- [ ] **Step 2: Verify the test fails because contracts do not exist**

Run: `uv run pytest tests/conversation/contracts/test_envelope.py -q`
Expected: collection fails with `ModuleNotFoundError: mika.conversation`.

- [ ] **Step 3: Implement frozen typed contracts**

Implement immutable dataclasses with tuple defaults. `ConversationEnvelope.visual_inputs`
returns current media followed by referenced media, deduplicated by URL. `TurnTrace.add()`
returns a replaced trace instead of mutating shared state.

- [ ] **Step 4: Verify contract tests pass**

Run: `uv run pytest tests/conversation/contracts/test_envelope.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mika/conversation tests/conversation/contracts
git commit -m "feat(conversation): add typed turn contracts"
```

### Task 2: Discord message normalization and reference resolution

**Files:**
- Create: `src/mika/discord/README.md`
- Create: `src/mika/discord/__init__.py`
- Create: `src/mika/discord/ingress/README.md`
- Create: `src/mika/discord/ingress/__init__.py`
- Create: `src/mika/discord/ingress/media.py`
- Create: `src/mika/discord/ingress/envelope.py`
- Test: `tests/discord/ingress/test_media.py`
- Test: `tests/discord/ingress/test_envelope.py`
- Modify: `src/mika/bot/events/message.py`

**Interfaces:**
- Consumes: contracts from Task 1.
- Produces: `media_from_message(message: discord.Message) -> tuple[MediaAsset, ...]`.
- Produces: `envelope_from_message(message: discord.Message, bot_user_id: int) -> ConversationEnvelope`.

- [ ] **Step 1: Write media normalization tests**

Cover attachments, image/video embeds, stickers, duplicate URLs, and unsupported embeds.
The expected behavior is one normalized asset per canonical URL with the original source.

- [ ] **Step 2: Write referenced-message tests**

```python
def test_reply_to_someone_elses_gif_preserves_author_and_visual_context() -> None:
    message = fake_message(
        content="that face when prod breaks",
        reference=fake_message(author_name="alice", embed_url="https://cdn/face.gif"),
    )

    envelope = envelope_from_message(message, bot_user_id=999)

    assert envelope.referenced is not None
    assert envelope.referenced.author_name == "alice"
    assert envelope.visual_inputs[0].kind == "gif"
```

- [ ] **Step 3: Verify both test modules fail for missing ingress adapters**

Run: `uv run pytest tests/discord/ingress -q`
Expected: collection fails for missing modules.

- [ ] **Step 4: Implement normalization without provider calls**

Resolve `message.reference.resolved` when it is a Discord message. Normalize forwarded
snapshots when exposed by discord.py. Do not fetch arbitrary referenced URLs. Preserve
reply author and text. Limit visual assets to four after deduplication.

- [ ] **Step 5: Replace legacy extraction helpers with compatibility delegates**

Keep `_media_from_message`, `_media_context`, and `_media_urls` temporarily, but implement
them through the new envelope/assets so existing callers remain green during migration.

- [ ] **Step 6: Verify ingress and legacy media tests pass**

Run: `uv run pytest tests/discord/ingress tests/test_message_media_context.py -q`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/mika/discord src/mika/bot/events/message.py tests/discord tests/test_message_media_context.py
git commit -m "refactor(discord): normalize message context"
```

### Task 3: Additive turn-trace persistence

**Files:**
- Create: `src/mika/persistence/conversations/README.md`
- Create: `src/mika/persistence/conversations/__init__.py`
- Create: `src/mika/persistence/conversations/models.py`
- Create: `src/mika/persistence/conversations/traces.py`
- Modify: `src/mika/persistence/models/__init__.py`
- Modify: `src/mika/persistence/engine.py`
- Test: `tests/persistence/conversations/test_traces.py`

**Interfaces:**
- Consumes: `TurnTrace` from Task 1.
- Produces: `TurnTraceRepository.add(trace: TurnTrace) -> None`.
- Produces: `TurnTraceRepository.recent(limit: int) -> list[StoredTurnTrace]`.
- Produces: `TurnTraceRepository.get(trace_id: str) -> StoredTurnTrace | None`.

- [ ] **Step 1: Write repository round-trip test**

The test creates an isolated SQLite engine, persists a trace with two stages, reloads it,
and asserts stage order, reasons, safe details, and durations survive exactly.

- [ ] **Step 2: Verify the repository test fails for missing modules**

Run: `uv run pytest tests/persistence/conversations/test_traces.py -q`
Expected: collection fails for missing repository.

- [ ] **Step 3: Implement additive models and repository**

Store trace header and stages in separate tables linked by trace ID. Store `details` as JSON
text after rejecting keys named `token`, `authorization`, `secret`, `content`, or `raw_text`.
Create tables through the existing metadata startup path; do not rewrite message rows.

- [ ] **Step 4: Verify persistence tests pass**

Run: `uv run pytest tests/persistence/conversations/test_traces.py tests/test_memory.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mika/persistence tests/persistence
git commit -m "feat(persistence): store turn stage traces"
```

### Task 4: Blind evaluation contracts and baseline runner

**Files:**
- Create: `src/mika/conversation/evaluation/README.md`
- Create: `src/mika/conversation/evaluation/__init__.py`
- Create: `src/mika/conversation/evaluation/cases.py`
- Create: `src/mika/conversation/evaluation/scoring.py`
- Create: `src/mika/conversation/evaluation/runner.py`
- Create: `tests/fixtures/conversation_benchmark_v1.json`
- Create: `tests/conversation/evaluation/test_runner.py`
- Create: `tools/run_conversation_benchmark.py`

**Interfaces:**
- Produces: `BenchmarkCase(case_id, category, turns, hidden_expectations)`.
- Produces: `CaseResult(case_id, visible_turn, latency_ms, score, failures)`.
- Produces: `run_cases(cases, responder) -> BenchmarkReport`.
- `responder` consumes only ordinary envelope turns and cannot access hidden expectations.

- [ ] **Step 1: Write leakage and scoring tests**

```python
async def test_runner_never_passes_hidden_expectations_to_responder() -> None:
    seen: list[ConversationEnvelope] = []

    async def responder(envelope: ConversationEnvelope) -> VisibleTurn:
        seen.append(envelope)
        return VisibleTurn(reply="yeah that's absolutely you")

    case = benchmark_case(expected_intent="joke", forbidden_phrases=("as an assistant",))
    await run_cases((case,), responder)

    assert "expected_intent" not in repr(seen[0])
    assert "benchmark" not in seen[0].text.lower()
```

- [ ] **Step 2: Verify evaluation tests fail for missing modules**

Run: `uv run pytest tests/conversation/evaluation/test_runner.py -q`
Expected: collection fails for missing evaluation package.

- [ ] **Step 3: Implement deterministic scoring**

Score participation choice, allowed action combinations, reply length, forbidden assistant
phrases, expected tool need, and media-context use. Keep semantic quality as an optional
post-run judge field; deterministic scores must run offline.

- [ ] **Step 4: Add at least 48 synthetic cases**

Use balanced categories: direct chat, ambient silence, callback, joke, sarcasm, flirt,
comfort, criticism, current facts, explicit media, proactive reaction, proactive media,
static image context, GIF context, and reply-to-media context. Case prompts contain only
normal Discord dialogue. Hidden expectations live beside cases but never enter envelopes.

- [ ] **Step 5: Implement CLI runner and JSON report**

`tools/run_conversation_benchmark.py --mode legacy --output var/evaluation/baseline.json`
uses isolated channel IDs and writes aggregate/category metrics without modifying fixtures.

- [ ] **Step 6: Verify evaluation tests and offline dry run**

Run: `uv run pytest tests/conversation/evaluation -q`
Run: `uv run python tools/run_conversation_benchmark.py --dry-run`
Expected: tests pass; dry run validates all cases and reports zero prompt leakage.

- [ ] **Step 7: Commit**

```bash
git add src/mika/conversation/evaluation tests/conversation/evaluation tests/fixtures tools/run_conversation_benchmark.py
git commit -m "feat(evaluation): add blind conversation benchmark"
```

### Task 5: Trace the legacy production path

**Files:**
- Create: `src/mika/conversation/trace_service.py`
- Modify: `src/mika/ai/llm/client.py`
- Modify: `src/mika/bot/events/message.py`
- Test: `tests/conversation/test_trace_service.py`
- Modify: `tests/test_client.py`

**Interfaces:**
- Consumes: envelope, turn, tool outcome, policy outcome, execution outcome.
- Produces: persisted stages named `ingress`, `context`, `retrieval`, `tools`,
  `generation`, `policy`, and `execution`.

- [ ] **Step 1: Write complete-trace and redaction tests**

The test runs a fake provider turn and asserts every attempted stage appears in order,
failed stages carry typed reasons, and user text/provider raw output are absent from details.

- [ ] **Step 2: Verify trace tests fail because the service is missing**

Run: `uv run pytest tests/conversation/test_trace_service.py -q`
Expected: collection fails for missing service.

- [ ] **Step 3: Implement trace service and legacy adapters**

Measure stages with `time.monotonic()`. Add optional trace hooks to `LLMClient.reply` without
changing its visible return contract. The Discord handler supplies the normalized envelope,
records policy and execution results, then persists once in a `finally` path.

- [ ] **Step 4: Verify trace, client, and message tests pass**

Run: `uv run pytest tests/conversation/test_trace_service.py tests/test_client.py tests/test_message_media_context.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mika/conversation/trace_service.py src/mika/ai/llm/client.py src/mika/bot/events/message.py tests
git commit -m "feat(conversation): trace legacy turn stages"
```

### Task 6: Operator diagnostics read model and routes

**Files:**
- Create: `src/mika/web/diagnostics/README.md`
- Create: `src/mika/web/diagnostics/__init__.py`
- Create: `src/mika/web/diagnostics/traces.py`
- Create: `src/mika/web/routes/diagnostics.py`
- Create: `src/mika/web/templates/diagnostics.html`
- Modify: `src/mika/web/app.py`
- Modify: `src/mika/web/templates/base.html`
- Modify: `docs/DASHBOARD.md`
- Test: `dev-testing/test_diagnostics.py`

**Interfaces:**
- Consumes: `TurnTraceRepository` read methods.
- Produces: authenticated `/diagnostics` page and `/api/diagnostics/traces` endpoint.

- [ ] **Step 1: Write auth, list, detail, and redaction tests**

Verify unauthenticated requests redirect; authenticated responses show stage names, reasons,
durations, and action outcomes; response bodies contain no stored message content or secrets.

- [ ] **Step 2: Verify diagnostics tests fail with 404**

Run: `uv run pytest dev-testing/test_diagnostics.py -q`
Expected: authenticated diagnostics route returns 404.

- [ ] **Step 3: Implement diagnostics read model and routes**

The route depends on repository interfaces only. Render a compact stage timeline and summary
cards for fallback, tools, media, and execution. Do not add frontend business logic.

- [ ] **Step 4: Verify diagnostics and dashboard tests pass**

Run: `uv run pytest dev-testing/test_diagnostics.py dev-testing/test_dashboard.py -q`
Expected: all tests pass.

- [ ] **Step 5: Run complete verification and Prowl safety checks**

Run: `make check`
Run: `prowl-agent changed --format markdown`
Run: `prowl-agent doctor --format markdown`
Expected: all project checks pass; no new cycles or dangling references.

- [ ] **Step 6: Commit**

```bash
git add src/mika/web frontend docs/DASHBOARD.md dev-testing/test_diagnostics.py
git commit -m "feat(web): expose turn diagnostics"
```

## Plan self-review

- The plan covers typed contracts, referenced media, trace persistence, blind evaluation,
  legacy-path tracing, and operator visibility from the umbrella design's first migration slice.
- Every production behavior task starts with a failing test and an explicit failure reason.
- Later tasks consume exact interfaces declared by earlier tasks.
- The plan deliberately defers participation, personality, proactive media, and retrieval
  replacement until this baseline can measure them.
