# Task 5: Profile Consolidation and Rollback

## RED

`uv run pytest tests/conversation/relationships/test_consolidation.py -q` failed at collection
before implementation with `ModuleNotFoundError: No module named
'mika.conversation.relationships.consolidation'`.

The public package export was also verified test-first: the focused suite failed with
`ImportError: cannot import name 'RelationshipConsolidator'` before the package export was added.

## GREEN

- `uv run pytest tests/conversation/relationships/test_consolidation.py -q` — 8 passed.
- `uv run pytest tests/conversation/relationships -q` — 43 passed.
- `make lint` — passed.
- `make types` — passed.
- `make check` — passed: ruff check, ruff format check, mypy, and the full pytest suite.

## Scope

Added pure typed profile and consolidation modules. Consolidation normalizes claims, promotes
candidate evidence through the existing activation policy, expires stale inference, preserves
temporal contradictions, makes correction replacement explicit, merges duplicate source support
without confidence inflation, and returns a rollback-safe result when protected predecessor claims
would be lost. Runtime and persistence integration remain intentionally out of scope.

## Concerns

None. The unrelated `AGENTS.md` worktree modification was preserved.

## Fix Round 1

### RED

Three new regression tests failed before the fix:

- Noncanonical evidence key/value formatting left a normalized reaction candidate in `candidate`.
- Reversing equal-timestamp claims produced a spurious profile version.
- A terminal duplicate predecessor claim caused a false rollback rejection and duplicate salvage.

### GREEN

- `uv run pytest tests/conversation/relationships/test_consolidation.py -q` — 11 passed.
- `uv run pytest tests/conversation/relationships -q` — 46 passed.
- `make lint` — passed.
- `make types` — passed.

Evidence proposals are normalized before activation, profile entry ordering now has deterministic
secondary keys, and duplicate merge output retains every claim lifecycle state for claim-granular
predecessor protection.
