"""Application-owned lifecycle adapter for conversation trace persistence."""

from __future__ import annotations

from mika.conversation.contracts import TurnTrace
from mika.persistence.conversations.traces import TurnTraceRepository
from mika.persistence.engine import session


class ManagedTurnTraceRepository:
    """Open a short database session for each completed engine trace."""

    async def add(self, trace: TurnTrace) -> None:
        """Persist one trace without leaking session ownership into orchestration."""
        async with session() as active:
            await TurnTraceRepository(active).add(trace)
