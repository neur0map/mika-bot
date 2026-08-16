"""Privacy-safe diagnostic records for conversation stages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class StageTrace:
    """Outcome and timing for one named conversation stage."""

    stage: str
    outcome: str
    reason: str | None
    duration_ms: float
    details: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class TurnTrace:
    """Ordered diagnostic stages associated with one Discord message."""

    trace_id: str
    message_id: str
    channel_id: str
    stages: tuple[StageTrace, ...] = ()

    def add(self, stage: StageTrace) -> TurnTrace:
        """Return a trace with `stage` appended without mutating the original."""
        return replace(self, stages=(*self.stages, stage))
