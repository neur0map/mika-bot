# Staged Conversation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Mika's coupled provider/message-handler decision path with typed context, participation, tool, generation, and action stages that preserve the current provider and Discord behavior while making each decision independently testable.

**Architecture:** `conversation/engine.py` orchestrates small feature-owned stages over the existing platform-neutral envelope. Discord adapts messages and executes a final action plan; providers only generate a candidate. Context selection happens before generation and observation after execution, with each stage contributing to the existing privacy-safe turn trace.

**Tech Stack:** Python 3.12, frozen dataclasses, protocols, async SQLAlchemy, discord.py, pytest, pytest-asyncio, existing ACP/OpenAI-compatible providers.

## Global Constraints

- Prowl Agent is required before edits and for every change-impact review.
- The subscription-backed ACP provider remains primary and the HTTP provider remains fallback.
- Discord Bot API is the only Discord integration.
- Production behavior changes start with a failing test.
- Raw user text, provider output, secrets, and authorization values never enter trace details.
- Public interfaces are fully typed; Python files stay below 500 lines and target 300.
- Each new directory contains a README defining purpose and dependencies.
- Silence, reply, reaction, and media are independent actions; visible output never fabricates an executed action.

---

### Task 1: Context selection and observation boundaries

**Files:**
- Create: `src/mika/conversation/context/README.md`
- Create: `src/mika/conversation/context/__init__.py`
- Create: `src/mika/conversation/context/contracts.py`
- Create: `src/mika/conversation/context/selector.py`
- Create: `src/mika/conversation/context/observer.py`
- Test: `tests/conversation/context/test_selector.py`

**Interfaces:**
- Produces: `SelectedContext(history: tuple[ContextMessage, ...], memory: str, avoid_phrases: tuple[str, ...])`.
- Produces: `ContextSelector.select(envelope: ConversationEnvelope) -> SelectedContext`.
- Produces: `TurnObservation(envelope, action, intent, confidence)` and `TurnObserver.observe(observation) -> None`.

- [ ] **Step 1: Write failing selector tests** proving channel history stays ordered, user names survive, assistant phrases are bounded, and raw history is not placed in trace details.
- [ ] **Step 2: Run** `uv run pytest tests/conversation/context/test_selector.py -q` and verify missing-module failure.
- [ ] **Step 3: Implement contracts and a selector over `LocalMemory`; implement an observer over the same storage boundary without importing Discord or providers.**
- [ ] **Step 4: Run focused tests, Ruff, and mypy** for `conversation/context`.
- [ ] **Step 5: Run** `prowl-agent changed --format markdown`, review blast radius, and commit `feat(context): add turn selection and observation boundaries`.

### Task 2: Participation planning

**Files:**
- Create: `src/mika/conversation/participation/README.md`
- Create: `src/mika/conversation/participation/__init__.py`
- Create: `src/mika/conversation/participation/contracts.py`
- Create: `src/mika/conversation/participation/planner.py`
- Test: `tests/conversation/participation/test_planner.py`

**Interfaces:**
- Produces: `ParticipationDecision(mode: Literal["reply", "react", "media", "observe"], reason: str, confidence: float)`.
- Produces: `ParticipationPlanner.plan(envelope, selected_context) -> ParticipationDecision`.
- Consumes only structural signals, bounded lexical social cues, reply relationship, and media presence; it does not call the provider.

- [ ] **Step 1: Write table-driven failing tests** for direct mention, direct question, private logistics silence, punchline invitation, callback, comfort, reply-to-media, and unsupported empty chatter.
- [ ] **Step 2: Run** `uv run pytest tests/conversation/participation/test_planner.py -q` and verify missing-module failure.
- [ ] **Step 3: Implement conservative deterministic candidate planning.** Direct address replies; private/logistical human-to-human messages observe; high-signal jokes, callbacks, celebrations, comfort, and referenced media may participate; ambiguous chatter observes.
- [ ] **Step 4: Run focused tests and the 48-case offline fixture validation.**
- [ ] **Step 5: Use Prowl changed/impact and commit** `feat(participation): classify social invitations`.

### Task 3: Tool eligibility and execution contracts

**Files:**
- Create: `src/mika/conversation/tools/README.md`
- Create: `src/mika/conversation/tools/__init__.py`
- Create: `src/mika/conversation/tools/contracts.py`
- Create: `src/mika/conversation/tools/planner.py`
- Create: `src/mika/conversation/tools/executor.py`
- Modify: `src/mika/ai/llm/tools/registry.py`
- Test: `tests/conversation/tools/test_planner.py`
- Test: `tests/conversation/tools/test_executor.py`

**Interfaces:**
- Produces: `ToolPlan(names: tuple[str, ...], reason: str)` and `ToolOutcome(name, status, summary, duration_ms)`.
- Produces: `ToolPlanner.plan(envelope, participation) -> ToolPlan`.
- Produces: `ToolExecutor.execute(plan, envelope) -> tuple[ToolOutcome, ...]`.

- [ ] **Step 1: Write failing tests** proving current facts expose web search, explicit/proactive media exposes media search, casual jokes expose neither, and unknown tools return a typed failure.
- [ ] **Step 2: Verify RED** with the focused pytest paths.
- [ ] **Step 3: Implement task-scoped schemas and execution around the existing registry.** Do not expose every registered tool to every provider call.
- [ ] **Step 4: Verify focused tests plus `tests/test_client.py` and provider tests.**
- [ ] **Step 5: Use Prowl changed/impact and commit** `refactor(tools): add task-scoped planning boundary`.

### Task 4: Candidate generation and response parsing extraction

**Files:**
- Create: `src/mika/conversation/generation/README.md`
- Create: `src/mika/conversation/generation/__init__.py`
- Create: `src/mika/conversation/generation/prompt.py`
- Create: `src/mika/conversation/generation/parser.py`
- Create: `src/mika/conversation/generation/service.py`
- Modify: `src/mika/ai/llm/client.py`
- Test: `tests/conversation/generation/test_parser.py`
- Test: `tests/conversation/generation/test_service.py`

**Interfaces:**
- Produces: `GenerationService.generate(envelope, context, participation, tools, trace) -> MikaTurn`.
- The service consumes the configured primary/fallback providers; the parser owns schema repair, action bounds, response-length bounds, and media eligibility.

- [ ] **Step 1: Write failing parser/service tests** for strict JSON, malformed fallback, concise social output, direct-question recovery, provider fallback, and no raw provider output in traces.
- [ ] **Step 2: Verify RED** because the generation package is absent.
- [ ] **Step 3: Move generation, parsing, and prompt assembly out of `LLMClient`; retain `LLMClient.reply` as a compatibility facade.**
- [ ] **Step 4: Verify client, provider, social-turn, and generation tests. Confirm `client.py` is under 300 lines.**
- [ ] **Step 5: Use Prowl changed/impact and commit** `refactor(generation): isolate provider turn service`.

### Task 5: Action planning and Discord execution

**Files:**
- Create: `src/mika/conversation/actions/README.md`
- Create: `src/mika/conversation/actions/__init__.py`
- Create: `src/mika/conversation/actions/contracts.py`
- Create: `src/mika/conversation/actions/planner.py`
- Create: `src/mika/discord/execution/README.md`
- Create: `src/mika/discord/execution/__init__.py`
- Create: `src/mika/discord/execution/executor.py`
- Modify: `src/mika/bot/events/message.py`
- Test: `tests/conversation/actions/test_planner.py`
- Test: `tests/discord/execution/test_executor.py`

**Interfaces:**
- Produces: `ActionPlan(reply: str, reactions: tuple[str, ...], media: MediaRequest | None, silence_reason: str | None)`.
- Produces: `ExecutionResult(reply_message_id, applied_reactions, media_url, failures)`.
- Discord executor performs network actions; action planner applies cooldowns/diversity without importing Discord.

- [ ] **Step 1: Write failing tests** for text-only, reaction-only, media-only, combined restraint, cooldown independence, partial Discord failure, and truthful execution results.
- [ ] **Step 2: Verify RED** for both packages.
- [ ] **Step 3: Implement action planning and Discord execution; replace handler loops with the executor boundary.**
- [ ] **Step 4: Verify message, policy, media, archive, and execution tests. Confirm `message.py` is under 220 lines.**
- [ ] **Step 5: Use Prowl changed/impact and commit** `refactor(discord): isolate visible action execution`.

### Task 6: Engine orchestration, legacy migration, and benchmark adapter

**Files:**
- Create: `src/mika/conversation/engine.py`
- Modify: `src/mika/bot/client.py`
- Modify: `src/mika/bot/events/message.py`
- Modify: `tools/run_conversation_benchmark.py`
- Test: `tests/conversation/test_engine.py`
- Modify: `tests/conversation/evaluation/test_runner.py`

**Interfaces:**
- Produces: `ConversationEngine.handle(envelope) -> ActionPlan` and `ConversationEngine.observe(envelope, action, execution) -> None`.
- Each handle call records stages `ingress`, `context`, `participation`, `tools`, `generation`, `policy`; observation adds `execution` and persists once.

- [ ] **Step 1: Write a failing end-to-end engine test** with real stage objects and local repositories, replacing only the external provider and Discord network boundaries.
- [ ] **Step 2: Verify RED** because `ConversationEngine` is absent.
- [ ] **Step 3: Implement orchestration and wire BotApp/message ingress to it; keep CLI and learning callers on the compatibility facade until their dedicated migration.**
- [ ] **Step 4: Update the benchmark adapter to record actual tool/media-context use from stage outcomes rather than inference.**
- [ ] **Step 5: Run** `uv run python tools/run_conversation_benchmark.py --dry-run`, `make check`, `prowl-agent changed --format markdown`, and `prowl-agent doctor`; resolve new failures/cycles.
- [ ] **Step 6: Commit** `feat(conversation): route Discord turns through staged engine`.

## Self-review

- Spec coverage: this plan covers context selection/observation, participation, scoped tools, generation, actions, Discord execution, tracing, and benchmark truthfulness. GIF frame extraction, affinity/FTS retrieval, user facts, feedback learning, command ability folders, and dashboard views intentionally remain independent plans because each is separately shippable.
- Placeholder scan: no TBD/TODO or undefined implementation steps remain.
- Type consistency: `ConversationEnvelope` enters all stages; `SelectedContext`, `ParticipationDecision`, `ToolPlan`, `MikaTurn`, `ActionPlan`, and `ExecutionResult` form the only forward data flow.
