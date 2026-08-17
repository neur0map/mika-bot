# conversation/

Platform-neutral Discord member behavior. This domain owns turn contracts, context,
participation, personality, retrieval, perception, generation, actions, and evaluation.
It may depend on `core` and persistence interfaces, but never on `discord.*`.

`skills/natural_expression/` learns aggregate human writing distributions from the local archive,
provides conservative Unicode and guild emoji guidance, and records only bounded style fingerprints
after Discord successfully renders an action.

`evaluation/relationship_memory.py` provides a versioned, stateful replay benchmark for scoped
recall, corrections, contradictions, sensitive abstention, attribution, and local latency. It
writes content-free case artifacts and blocks rollout on privacy or quality regressions.
