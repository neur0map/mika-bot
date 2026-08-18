# Relationship memory

This package provides immutable relationship-memory contracts, deterministic relation
classification, scoped candidate construction, inspectable hybrid scoring, and whole-tier budgeted
rendering. The orchestration service coordinates injected extraction, persistence, activation,
retrieval, and consolidation boundaries without importing Discord or a model provider. Runtime
telemetry retains only bounded operation timings, counts, statuses, policy versions, and hashed
correlation identifiers. Durable telemetry sinks must implement the explicit
`RelationshipTelemetrySink` contract: writes propagate cancellation after completing bounded
cleanup. This lets shutdown await real sink cleanup without relying on private asyncio state.
