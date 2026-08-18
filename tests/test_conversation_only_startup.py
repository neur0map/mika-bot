"""Conversation-only bot startup tests."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

import mika.bot.client as client_module
from mika.bot.client import BotApp


async def test_setup_hook_never_registers_application_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_all = Mock()
    monkeypatch.setattr(client_module, "register_all", register_all, raising=False)
    monkeypatch.setattr(client_module, "init_db", AsyncMock())
    monkeypatch.setattr(BotApp, "_start_web", Mock())
    monkeypatch.setattr(client_module, "start_schedulers", Mock(return_value=None))

    bot = BotApp()
    bot.llm.startup = AsyncMock()
    bot.relationship_memory.ensure_policy_version = AsyncMock()
    try:
        await bot.setup_hook()
        register_all.assert_not_called()
    finally:
        await bot.close()


async def test_bot_retains_and_closes_scheduler_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduler = Mock()
    scheduler.close = AsyncMock()
    monkeypatch.setattr(client_module, "init_db", AsyncMock())
    monkeypatch.setattr(BotApp, "_start_web", Mock())
    monkeypatch.setattr(client_module, "start_schedulers", Mock(return_value=scheduler))

    bot = BotApp()
    bot.llm.startup = AsyncMock()
    bot.llm.shutdown = AsyncMock()
    bot.relationship_memory.ensure_policy_version = AsyncMock()
    await bot.setup_hook()

    await bot.close()

    scheduler.close.assert_awaited_once()


async def test_bot_drains_jobs_then_telemetry_before_provider_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    scheduler = Mock()
    scheduler.close = AsyncMock(side_effect=lambda: order.append("jobs"))
    monkeypatch.setattr(client_module, "init_db", AsyncMock())
    monkeypatch.setattr(BotApp, "_start_web", Mock())
    monkeypatch.setattr(client_module, "start_schedulers", Mock(return_value=scheduler))

    bot = BotApp()
    bot.llm.startup = AsyncMock()
    bot.llm.shutdown = AsyncMock(side_effect=lambda: order.append("provider"))
    bot.relationship_service.telemetry.close = AsyncMock(
        side_effect=lambda: order.append("telemetry")
    )
    bot.relationship_memory.ensure_policy_version = AsyncMock()
    await bot.setup_hook()

    await bot.close()

    assert order == ["jobs", "telemetry", "provider"]


async def test_bot_close_bounds_production_sink_and_awaits_its_cleanup() -> None:
    cleanup_completed = asyncio.Event()
    bot = BotApp()
    bot.llm.shutdown = AsyncMock()

    async def slow_write(record: object) -> None:
        del record
        try:
            await asyncio.Event().wait()
        finally:
            cleanup_completed.set()

    bot.relationship_memory.record_operation_write = AsyncMock(side_effect=slow_write)
    bot.relationship_service.telemetry.emit(
        "retrieval",
        "ok",
        correlation_id="wedged",
        duration_ms=0,
        candidate_count=0,
        selected_count=0,
        rejected_count=0,
        estimated_tokens=0,
        fallback_reason=None,
        profile_changed=None,
        policy_version_id=None,
    )

    await asyncio.wait_for(bot.close(), timeout=4.5)

    bot.llm.shutdown.assert_awaited_once()
    assert cleanup_completed.is_set()


def test_bot_composes_relationship_observation_job() -> None:
    bot = BotApp()

    assert bot.relationship_job is not None
