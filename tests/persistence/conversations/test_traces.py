"""Turn trace repository round-trip and privacy tests."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mika.conversation.contracts import StageTrace, TurnTrace
from mika.persistence.base import Base
from mika.persistence.conversations.traces import TurnTraceRepository


async def test_trace_round_trip_preserves_order_and_details() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    trace = TurnTrace(
        trace_id="trace-1",
        message_id="message-1",
        channel_id="channel-1",
        stages=(
            StageTrace("context", "ready", "history found", 1.25, {"messages": 4}),
            StageTrace("participation", "reply", None, 2.5, {"confidence": 0.9}),
        ),
    )

    async with sessions() as session:
        repository = TurnTraceRepository(session)
        await repository.add(trace)
        stored = await repository.get("trace-1")

    assert stored is not None
    assert stored.trace_id == "trace-1"
    assert stored.message_id == "message-1"
    assert [stage.stage for stage in stored.stages] == ["context", "participation"]
    assert [stage.reason for stage in stored.stages] == ["history found", None]
    assert [stage.duration_ms for stage in stored.stages] == [1.25, 2.5]
    assert [stage.details for stage in stored.stages] == [
        {"messages": 4},
        {"confidence": 0.9},
    ]

    await engine.dispose()


async def test_trace_rejects_sensitive_detail_keys() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    trace = TurnTrace(
        trace_id="trace-secret",
        message_id="message-1",
        channel_id="channel-1",
        stages=(StageTrace("provider", "done", None, 1.0, {"token": "unsafe"}),),
    )

    async with sessions() as session:
        with pytest.raises(ValueError, match="sensitive detail key"):
            await TurnTraceRepository(session).add(trace)

    await engine.dispose()
