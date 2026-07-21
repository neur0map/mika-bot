"""OpenAI-compatible provider transport tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from mika.ai.llm.providers.openai_compatible import OpenAICompatibleProvider
from mika.ai.llm.turn import mika_turn_response_format


async def test_complete_forwards_strict_schema_response_format(monkeypatch: Any) -> None:
    provider = OpenAICompatibleProvider(base_url="https://example.invalid/v1", api_key="test")
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content='{"reply":"ok"}', tool_calls=[]))
            ]
        )
    )
    monkeypatch.setattr(provider._client.chat.completions, "create", create)

    response_format = mika_turn_response_format()
    await provider.complete(
        [{"role": "user", "content": "hello"}],
        model="openai/gpt-5.4-mini",
        response_format=response_format,
    )

    assert create.await_args is not None
    assert create.await_args.kwargs["response_format"] == response_format
