"""Prompt assembly: the persona name and recalled memory reach the system prompt."""

from __future__ import annotations

from mika.ai.llm.chat.prompt import build_system_prompt
from mika.core.config import get_settings


def test_prompt_includes_persona_name() -> None:
    assert get_settings().persona.name in build_system_prompt("")


def test_prompt_includes_memory_context() -> None:
    assert "a remembered fact" in build_system_prompt("a remembered fact")


def test_prompt_guides_flirty_comedy_without_forcing_it() -> None:
    prompt = build_system_prompt("")
    assert "Read flirting as a vibe" in prompt
    assert "do not force it" in prompt
    assert "callbacks" in prompt


def test_prompt_guides_media_reactivity_without_captioning() -> None:
    prompt = build_system_prompt("")
    assert "Incoming GIFs" in prompt
    assert "not captions to describe" in prompt


def test_prompt_blocks_creepy_flirt_dependency() -> None:
    prompt = build_system_prompt("")
    assert "never possessive" in prompt
    assert "no jealousy" in prompt
    assert "no emotional dependency" in prompt


def test_prompt_guides_discord_social_selectivity() -> None:
    prompt = build_system_prompt("")
    assert "Do not hijack human-to-human conversations" in prompt
    assert "public channels stay less intimate" in prompt
    assert "reaction-only" in prompt
