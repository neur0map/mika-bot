# Conversation evaluation

This package loads blind social-conversation cases and scores outputs only after generation.
The relationship benchmark replays chronological visible turns through an isolated temporary
SQLite store and the production relationship service/retriever. Hidden expectations never cross
the replay boundary. Per-case artifacts contain IDs, decisions, counts, timings, and scores only.
Archive-cursor continuation stays in the archive/operator test suite. External recall without
source-scope attribution is informational and never rollout-eligible.
