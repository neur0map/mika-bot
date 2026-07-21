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
    monkeypatch.setattr(client_module, "start_schedulers", Mock())

    bot = BotApp()
    bot.llm.startup = AsyncMock()
    try:
        await bot.setup_hook()
        register_all.assert_not_called()
    finally:
        await bot.close()
