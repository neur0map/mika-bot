# Task 6 execution report

## Slice A: relationship-memory orchestration service

### RED

- `uv run pytest tests/conversation/relationships/test_service.py -q` failed during collection with
  `ModuleNotFoundError` for the missing `mika.conversation.relationships.service` module.
- The focused persistence regression failed with `AttributeError` for the missing
  `claims_for_subject` repository boundary.

### GREEN

- Added a typed `RelationshipMemoryService` with injected repository, extractor, activation,
  classifier, retriever, consolidator, and optional pending-source boundaries.
- Added bounded `observe_turn`, `recall`, `consolidate_user`, and `run_pending_observations` APIs.
- Added content-free policy attribution for observations and recall traces, deterministic
  idempotency keys, correction supersession, cursor retry behavior, and no-op profile publication.
- Added primitive `claims_for_subject` and `evidence_for_claims` reads so consolidation receives
  candidates, terminal states, and source-distinct evidence without a schema change.
- Focused RED targets passed: `9 passed`.

### Remaining integration scope

- Engine visible-action ordering, observer wiring, scheduler lifecycle, configuration, telemetry
  aggregation, and LLM-provider composition remain in Task 6 slice B.
- Persistence currently has no general transition for writing consolidation-produced `expired`
  or `disputed` states. Slice A publishes candidate promotions and profiles but does not mutate
  those unsupported lifecycle states.

## Slice A repair 1: claim-isolated evidence and correction targets

### RED

- The same-key isolation regression failed because an explicit claim in one scope caused an
  unrelated repeated-behavior claim with another value and scope to become active.
- The multiple-preference correction regression failed because the newest same-kind game claim was
  selected for a drink correction, then persistence rejected the mismatched predecessor key.

### GREEN

- Consolidation accepts an exact `evidence_by_claim_id` map while retaining the legacy key-based
  argument for existing pure-consolidator callers. The service now uses only exact persisted
  claim/evidence associations.
- Correction predecessor selection requires normalized key, subject, kind, and exact scope, and a
  replacement writes its predecessor's canonical stored key.
- Focused service and consolidation verification passed: `22 passed`.

## Slice A repair 2: complete reads and atomic consolidation lifecycle

### RED

- A 1,001-claim persistence regression returned only the oldest 1,000 claims, excluding the newest
  candidate and its policy-attributed evidence.
- A service correction regression left the newest active target unlinked because correction
  discovery received only the older 1,000 history rows.
- A lossy-consolidator regression was not rejected because the service did not load and map the
  active predecessor profile.
- Consolidation left a stale inference in `candidate` because only candidate-to-active changes were
  persisted, and an unchanged profile remained attached to the prior policy version.
- Atomic publication initially failed with the missing primitive `ClaimTransitionRecord` and
  `RelationshipMemoryRepository.publish_consolidation` API.

### GREEN

- Internal consolidation history uses deterministic keyset pages and evidence IDs are chunked,
  merged, and globally sorted, so neither consolidation nor correction discovery silently truncates.
- The service maps the active rendered profile back to claim-bearing domain entries from complete
  history and passes it to the consolidator, preserving protected-anchor rejection without a schema
  migration.
- Added a persistence-owned atomic publication transaction accepting primitive lifecycle records.
  It applies candidate/active transitions to active, expired, disputed, or superseded states where
  allowed, inserts the immutable profile, advances its head, and commits once. Validation or insert
  failure rolls the entire unit back.
- Profile no-op detection now includes the effective policy version, so identical content is
  republished when policy attribution changes. Observation evidence retains its effective policy ID.

Verification:

```text
Focused service, consolidation, and persistence suites: 52 passed
ruff check: All checks passed!
ruff format --check: 346 files already formatted
mypy src: Success: no issues found in 223 source files
pytest: 541 passed, 3 warnings in 50.79s
```

The warnings were two existing dependency deprecations and one unrelated aiosqlite worker-thread
shutdown warning from `dev-testing/test_anime.py`.

## Slice A repair 2 review round 1: structured profiles and safe reversion

### RED

- Re-consolidating a profile containing `Tea; coffee` raised
  `active relationship profile cannot be mapped to source claims` because predecessor recovery
  split the rendered overview on `; `.
- The profile-link persistence regression first failed because `ProfileClaimLinkRecord` did not
  exist, then returned an empty link tuple after the primitive DTO was introduced.
- Same-policy A to B to A publication raised `profile version already exists`, rolling back the
  candidate transition that shared the publication transaction.
- A full `AffinityRetriever` regression could not commit an active-to-disputed transition because
  consolidation salvaged the disputed claim back into the prompt profile.

### GREEN

- Added the additive `relationship_profile_claim_links` table with profile version, claim identity,
  layer, and entry position only. It stores no transcript or raw observation content and is exposed
  through primitive `ProfileClaimLinkRecord` values on `ProfileVersionRecord`.
- Service publication writes deterministic profile links and includes them in version identity.
  Predecessor reconstruction now uses those links plus claim records and verifies the reconstructed
  index and overview exactly; it never parses display delimiters.
- Publication validates that linked claims belong to the profile subject and are active, and that
  every linked claim behind an active head remains active after staged transitions. Disputed,
  expired, and superseded results are prompt-inactive and cannot be salvaged into a new profile.
- An existing immutable profile version with identical body, policy, and links is reused and its
  head repointed. A conflicting reuse still fails, while A to B to A commits accompanying lifecycle
  transitions atomically.
- Full DM relationship retrieval after active-to-disputed consolidation contains neither the claim
  candidate nor its prior profile text.

Verification:

```text
Focused persistence, service, consolidation, and retrieval suites: 65 passed
ruff check: All checks passed!
ruff format --check: 347 files already formatted
mypy src: Success: no issues found in 223 source files
pytest: 545 passed, 2 warnings in 56.27s
```

The two warnings are the existing discord.py `audioop` and FastAPI/Starlette `httpx`
deprecations.
