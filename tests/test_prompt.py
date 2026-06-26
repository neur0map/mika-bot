"""Prompt assembly: the persona name and recalled memory reach the system prompt."""

from __future__ import annotations

from mika.ai.llm.chat.prompt import build_system_prompt
from mika.core.config import get_settings


def test_prompt_includes_persona_name() -> None:
    assert get_settings().persona.name in build_system_prompt("")


def test_prompt_includes_memory_context() -> None:
    assert "a remembered fact" in build_system_prompt("a remembered fact")
