"""Privacy-safe collection of ordered production turn stages."""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Protocol

from mika.conversation.contracts import StageTrace, TurnTrace

_DROP_KEYS = frozenset(
    {"token", "authorization", "secret", "content", "raw_text", "user_text", "prompt"}
)


class TraceRepository(Protocol):
    """Minimal persistence boundary used by the trace collector."""

    async def add(self, trace: TurnTrace) -> None: ...


def _safe_details(details: Mapping[str, object] | None) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in (details or {}).items():
        normalized = key.casefold()
        if normalized in _DROP_KEYS:
            continue
        if normalized in {"provider_output", "raw_output"}:
            safe[f"{normalized}_present"] = bool(value)
            continue
        if isinstance(value, Mapping):
            safe[key] = _safe_details(value)
        elif isinstance(value, (str, int, float, bool)) or value is None:
            safe[key] = value
    return safe


class TurnTraceService:
    """Build and persist one immutable turn trace."""

    def __init__(self, trace_id: str, message_id: str, channel_id: str) -> None:
        self._trace = TurnTrace(trace_id, message_id, channel_id)

    @property
    def trace(self) -> TurnTrace:
        """Return the immutable trace accumulated so far."""
        return self._trace

    def record(
        self,
        stage: str,
        outcome: str,
        *,
        reason: str | None = None,
        duration_ms: float = 0.0,
        details: Mapping[str, object] | None = None,
    ) -> None:
        """Append one redacted stage outcome."""
        self._trace = self._trace.add(
            StageTrace(stage, outcome, reason, duration_ms, _safe_details(details))
        )

    @contextmanager
    def measure(self, stage: str, *, details: Mapping[str, object] | None = None) -> Iterator[None]:
        """Measure a stage and record success or its exception type."""
        started = time.monotonic()
        try:
            yield
        except Exception as error:
            self.record(
                stage,
                "failed",
                reason=type(error).__name__,
                duration_ms=(time.monotonic() - started) * 1000,
                details=details,
            )
            raise
        self.record(
            stage,
            "ready",
            duration_ms=(time.monotonic() - started) * 1000,
            details=details,
        )

    async def persist(self, repository: TraceRepository) -> None:
        """Store the current trace through an additive repository boundary."""
        await repository.add(self._trace)
