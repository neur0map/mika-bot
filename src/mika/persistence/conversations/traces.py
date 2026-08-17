"""Repository for additive, privacy-safe turn traces."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mika.persistence.conversations.models import StoredStageTrace, StoredTurnTrace

_SENSITIVE_KEYS = frozenset({"token", "authorization", "secret", "content", "raw_text"})


class TraceStageRecord(Protocol):
    """Persistence-facing fields for one diagnostic stage."""

    @property
    def stage(self) -> str: ...

    @property
    def outcome(self) -> str: ...

    @property
    def reason(self) -> str | None: ...

    @property
    def duration_ms(self) -> float: ...

    @property
    def details(self) -> Mapping[str, object]: ...


class TurnTraceRecord(Protocol):
    """Persistence-facing fields for one ordered diagnostic trace."""

    @property
    def trace_id(self) -> str: ...

    @property
    def message_id(self) -> str: ...

    @property
    def channel_id(self) -> str: ...

    @property
    def stages(self) -> Sequence[TraceStageRecord]: ...


def _reject_sensitive_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).casefold() in _SENSITIVE_KEYS:
                raise ValueError(f"sensitive detail key is not allowed: {key}")
            _reject_sensitive_keys(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            _reject_sensitive_keys(nested)


class TurnTraceRepository:
    """Persist and query ordered conversation-stage diagnostics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, trace: TurnTraceRecord) -> None:
        """Persist a trace after rejecting sensitive diagnostic fields."""
        stages: list[StoredStageTrace] = []
        for position, stage in enumerate(trace.stages):
            _reject_sensitive_keys(stage.details)
            stages.append(
                StoredStageTrace(
                    position=position,
                    stage=stage.stage,
                    outcome=stage.outcome,
                    reason=stage.reason,
                    duration_ms=stage.duration_ms,
                    details_json=json.dumps(stage.details, sort_keys=True),
                )
            )
        self._session.add(
            StoredTurnTrace(
                trace_id=trace.trace_id,
                message_id=trace.message_id,
                channel_id=trace.channel_id,
                stages=stages,
            )
        )
        await self._session.commit()

    async def get(self, trace_id: str) -> StoredTurnTrace | None:
        """Return one trace by ID, including stages."""
        statement = (
            select(StoredTurnTrace)
            .options(selectinload(StoredTurnTrace.stages))
            .where(StoredTurnTrace.trace_id == trace_id)
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def recent(self, limit: int) -> list[StoredTurnTrace]:
        """Return the newest trace headers and stages first."""
        statement = (
            select(StoredTurnTrace)
            .options(selectinload(StoredTurnTrace.stages))
            .order_by(StoredTurnTrace.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.execute(statement)).scalars().all())
