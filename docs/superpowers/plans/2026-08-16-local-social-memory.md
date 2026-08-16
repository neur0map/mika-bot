# Local Social Memory Implementation Plan

## Goal

Give Mika durable, privacy-conscious awareness of recurring users without making an external vector
database mandatory. Retrieval must prefer same-user and same-channel evidence, surface explicit user
facts, incorporate feedback on Mika's visible messages, and remain bounded enough for every turn.

## Architecture decision

Prowl found an existing local recent-message database, optional Honcho semantic recall, reaction
feedback written only to the shared archive, and an FTS5 table in that optional archive. The primary
database is configured as SQLite by default but remains PostgreSQL-capable, so this slice will not
bind core behavior to SQLite-only FTS5 or add an embedding service. It will use bounded candidate
queries plus deterministic lexical scoring and affinity boosts. Honcho remains an optional second
recall source. This provides an embedded/local default now and preserves a narrow retriever protocol
for later embeddings.

## Task 1: Durable user facts and feedback

**Files:**
- Create `src/mika/persistence/conversations/social_models.py`
- Create `src/mika/persistence/conversations/social_memory.py`
- Modify `src/mika/persistence/models/__init__.py`
- Test `tests/persistence/conversations/test_social_memory.py`

- [ ] Write failing repository tests for fact upsert/deduplication, user isolation, feedback storage,
  and bounded message candidates.
- [ ] Add additive SQLAlchemy tables and repository methods; never store provider prompts or raw
  traces.
- [ ] Verify repository tests and schema creation.

## Task 2: Explicit-fact extraction and affinity retrieval

**Files:**
- Create `src/mika/conversation/context/facts.py`
- Create `src/mika/conversation/context/retrieval.py`
- Modify `src/mika/conversation/context/contracts.py`
- Modify `src/mika/conversation/context/selector.py`
- Test `tests/conversation/context/test_retrieval.py`

- [ ] Write failing tests for explicit self-facts only, corrections replacing older values,
  same-user affinity, same-channel lexical ranking, bounded output, and query-term privacy in traces.
- [ ] Implement conservative extraction and deterministic ranking over bounded repository candidates.
- [ ] Feed compact facts/recall/feedback summaries into `SelectedContext.memory`.

## Task 3: Observation and Discord reaction wiring

**Files:**
- Modify `src/mika/conversation/context/observer.py`
- Modify `src/mika/bot/events/reactions.py`
- Modify `src/mika/bot/client.py`
- Test `tests/conversation/context/test_observer.py`
- Modify `tests/test_feedback.py`

- [ ] Write failing tests that only explicit user facts are learned and only reactions to Mika's
  messages become feedback.
- [ ] Persist facts after a completed observation and persist normalized feedback through the local
  repository while retaining the shared archive event.
- [ ] Wire the local retriever into `ContextSelector` and verify graceful degradation on storage
  failures.

## Task 4: Verification and decision record

- [ ] Add privacy-safe retrieval counts to stage traces, never fact text or query text.
- [ ] Update memory documentation with the local lexical/affinity strategy and optional Honcho role.
- [ ] Run focused tests, `make check`, `prowl-agent changed --format markdown`, and
  `prowl-agent doctor`.
- [ ] Commit as independently reviewable persistence, retrieval, and wiring slices.
