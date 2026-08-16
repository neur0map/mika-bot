"""Codex/ACP provider: prompt flattening, stream filtering, and backend selection."""

from __future__ import annotations

import acp
import pytest
from acp.schema import AgentMessageChunk, AgentThoughtChunk

from mika.ai.llm.chat.pipeline import user_content
from mika.ai.llm.client import LLMClient
from mika.ai.llm.providers.codex_acp import (
    CodexACPProvider,
    _attach_notice,
    _render_prompt,
    _ReplyCollector,
    _split_content,
)
from mika.ai.llm.providers.factory import (
    build_fallback_provider,
    build_provider,
    is_codex_provider,
)
from mika.ai.llm.providers.openai_compatible import OpenAICompatibleProvider
from mika.core.config import LLMSettings


def _settings(**overrides: object) -> LLMSettings:
    """Settings built in isolation - the deployed .env must not leak into tests."""
    return LLMSettings(_env_file=None, **overrides)  # type: ignore[arg-type]


def _chunk(text: str) -> AgentMessageChunk:
    return AgentMessageChunk(content=acp.text_block(text), sessionUpdate="agent_message_chunk")


def _thought(text: str) -> AgentThoughtChunk:
    return AgentThoughtChunk(content=acp.text_block(text), sessionUpdate="agent_thought_chunk")


def test_render_prompt_folds_system_history_and_current_turn() -> None:
    prompt, _ = _render_prompt(
        [
            {"role": "system", "content": "You are Mika."},
            {"role": "user", "content": "carlos: hey"},
            {"role": "assistant", "content": "sup"},
            {"role": "user", "content": "carlos: you up?"},
        ]
    )

    assert "You are Mika." in prompt
    assert "Conversation so far:" in prompt
    assert "User: carlos: hey" in prompt
    assert "Mika: sup" in prompt
    # The latest turn is separated out so Codex answers it rather than the history.
    assert prompt.rstrip().endswith("User: carlos: you up?")
    assert "Conversation so far:\nUser: carlos: you up?" not in prompt


def test_render_prompt_skips_empty_content() -> None:
    prompt, _ = _render_prompt(
        [
            {"role": "system", "content": "   "},
            {"role": "user", "content": ""},
            {"role": "user", "content": "actual message"},
        ]
    )

    assert "User: actual message" in prompt
    assert "Conversation so far:" not in prompt


def test_render_prompt_forbids_tool_use() -> None:
    prompt, _ = _render_prompt([{"role": "user", "content": "hi"}])

    assert "Do not read files" in prompt


async def test_collector_keeps_replies_and_drops_reasoning() -> None:
    collector = _ReplyCollector()

    await collector.session_update("s1", _thought("thinking about it"))
    await collector.session_update("s1", _chunk("hey "))
    await collector.session_update("s1", _chunk("there"))

    assert collector.take("s1") == "hey there"


async def test_collector_isolates_concurrent_sessions() -> None:
    collector = _ReplyCollector()

    await collector.session_update("s1", _chunk("first"))
    await collector.session_update("s2", _chunk("second"))

    assert collector.take("s1") == "first"
    assert collector.take("s2") == "second"


async def test_collector_take_clears_the_buffer() -> None:
    collector = _ReplyCollector()
    await collector.session_update("s1", _chunk("once"))

    assert collector.take("s1") == "once"
    assert collector.take("s1") == ""


async def test_permission_requests_are_denied() -> None:
    collector = _ReplyCollector()

    response = await collector.request_permission("s1", tool_call=None, options=[])

    assert response.outcome.outcome == "cancelled"


async def test_filesystem_access_is_refused() -> None:
    collector = _ReplyCollector()

    with pytest.raises(acp.RequestError):
        await collector.read_text_file("s1", "/etc/passwd")
    with pytest.raises(acp.RequestError):
        await collector.write_text_file("s1", "/nowhere/x", "data")


def test_factory_selects_codex_backend() -> None:
    settings = _settings(provider="codex", codex_model="gpt-5.6-luna")

    assert is_codex_provider("codex")
    assert isinstance(build_provider(settings), CodexACPProvider)


def test_factory_defaults_to_openai_compatible() -> None:
    settings = _settings(provider="openrouter", api_key="k")

    assert not is_codex_provider("openrouter")
    assert isinstance(build_provider(settings), OpenAICompatibleProvider)


def test_codex_can_be_the_fallback_without_api_credentials() -> None:
    settings = _settings(provider="openrouter", api_key="k", fallback_provider="codex")

    # has_fallback stays False: Codex needs no key/base_url/model triple.
    assert not settings.has_fallback
    assert isinstance(build_fallback_provider(settings), CodexACPProvider)


def test_no_fallback_when_unconfigured() -> None:
    settings = _settings(provider="openrouter", api_key="k")

    assert build_fallback_provider(settings) is None


def test_scalar_reaction_is_recovered_not_dropped() -> None:
    """Codex answers `"reactions": "👀"` where the schema says array; keep it."""
    client = LLMClient.__new__(LLMClient)

    turn = LLMClient._parse_turn(
        client,
        '{"schema_version":"mika_turn.v2","reply":"yeah","reactions":"👀",'
        '"media":{"type":"none","query":null},"intent":"chat","confidence":0.9}',
    )

    assert turn.reactions == ("👀",)


def test_array_reactions_still_work() -> None:
    client = LLMClient.__new__(LLMClient)

    turn = LLMClient._parse_turn(
        client,
        '{"schema_version":"mika_turn.v2","reply":"ok","reactions":["❤️"],'
        '"media":{"type":"none","query":null},"intent":"comfort","confidence":0.9}',
    )

    assert turn.reactions == ("❤️",)


def test_unknown_scalar_reaction_is_ignored() -> None:
    client = LLMClient.__new__(LLMClient)

    turn = LLMClient._parse_turn(
        client,
        '{"schema_version":"mika_turn.v2","reply":"ok","reactions":"🦄",'
        '"media":{"type":"none","query":null},"intent":"chat","confidence":0.9}',
    )

    assert turn.reactions == ()


def test_user_content_is_plain_text_without_images() -> None:
    assert user_content("hello", None) == "hello"
    assert user_content("hello", []) == "hello"


def test_user_content_becomes_parts_with_images() -> None:
    parts = user_content("look at this", ["https://x/a.gif"])

    assert parts == [
        {"type": "text", "text": "look at this"},
        {"type": "image_url", "image_url": {"url": "https://x/a.gif"}},
    ]


def test_split_content_reads_plain_string() -> None:
    assert _split_content("just text") == ("just text", [])


def test_split_content_extracts_text_and_images() -> None:
    text, images = _split_content(
        [
            {"type": "text", "text": "what is this"},
            {"type": "image_url", "image_url": {"url": "https://x/a.gif"}},
            {"type": "image_url", "image_url": {"url": "https://x/b.png"}},
        ]
    )

    assert text == "what is this"
    assert images == ["https://x/a.gif", "https://x/b.png"]


def test_render_prompt_returns_images_separately_not_stringified() -> None:
    prompt, images = _render_prompt(
        [
            {"role": "system", "content": "You are Mika."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "carlos: whats this"},
                    {"type": "image_url", "image_url": {"url": "https://x/a.gif"}},
                ],
            },
        ]
    )

    assert images == ["https://x/a.gif"]
    # The URL must not leak into the text block - it rides as an ACP image block.
    assert "https://x/a.gif" not in prompt
    assert "User: carlos: whats this" in prompt


def test_attach_notice_counts_fetched_images_only() -> None:
    # Written after downloading, so a failed fetch never claims a visible image.
    assert "2 image(s) are attached" in _attach_notice(2)


def test_render_prompt_forbids_search_for_social_turns() -> None:
    prompt, _ = _render_prompt([{"role": "user", "content": "hi"}], allow_search=False)

    assert "Do not read files" in prompt
    assert "web search" not in prompt


def test_render_prompt_allows_search_when_tools_requested() -> None:
    """Mika's own web_search cannot run over ACP, so Codex must use its own."""
    prompt, _ = _render_prompt(
        [{"role": "user", "content": "whats the weather today"}], allow_search=True
    )

    assert "web search FIRST" in prompt
    assert "run shell commands" in prompt


def test_search_order_is_last_thing_the_model_reads() -> None:
    """The JSON contract sits mid-prompt; the search order must outrank it."""
    prompt, _ = _render_prompt(
        [{"role": "user", "content": "whats the weather today"}], allow_search=True
    )

    assert prompt.rstrip().endswith("is a failed answer.")


def test_no_search_trailer_on_social_turns() -> None:
    prompt, _ = _render_prompt([{"role": "user", "content": "lol"}], allow_search=False)

    assert "run your web search now" not in prompt
