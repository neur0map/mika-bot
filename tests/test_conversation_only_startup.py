"""Conversation-only bot startup tests."""

from __future__ import annotations

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


def test_bot_composes_relationship_observation_job() -> None:
    bot = BotApp()

    assert bot.relationship_job is not None
