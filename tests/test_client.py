"""LLM client output parsing guards."""

from __future__ import annotations

from typing import Any

from mika.ai.llm.client import LLMClient


def test_parse_turn_strips_labeled_output_leak() -> None:
    client = LLMClient()
    turn = client._parse_turn(
        "ugh tell me about it, the company really ruins it  "
        "reply: exactly, the pasta is a 10 but night is questionable media: none"
    )
    assert turn.reply == "exactly, the pasta is a 10 but night is questionable"
    assert turn.media.kind == "none"
    assert turn.parse_status == "labeled"


def test_parse_turn_accepts_json() -> None:
    client = LLMClient()
    turn = client._parse_turn(
        '{"schema_version":"mika_turn.v2",'
        '"reply":"night is fighting the flag allegations again",'
        '"reactions":["💀"],"media":{"type":"none","query":null},'
        '"intent":"sarcasm","confidence":0.82}'
    )
    assert turn.reply == "night is fighting the flag allegations again"
    assert turn.reactions == ("💀",)
    assert turn.intent == "sarcasm"
    assert turn.confidence == 0.82
    assert turn.schema_version == "mika_turn.v2"
    assert turn.parse_status == "json"


def test_parse_turn_clamps_unknown_intent_and_confidence() -> None:
    client = LLMClient()
    turn = client._parse_turn(
        '{"reply":"okay","reactions":[],"media":{"type":"none"},"intent":"random","confidence":4}'
    )
    assert turn.intent == "chat"
    assert turn.confidence == 1.0


def test_parse_turn_extracts_balanced_json_from_prose() -> None:
    client = LLMClient()
    turn = client._parse_turn(
        '```json\n{"reply":"brace joke {still text}","reactions":[],"media":'
        '{"type":"none","query":null},"intent":"joke","confidence":0.7}\n``` trailing'
    )
    assert turn.reply == "brace joke {still text}"
    assert turn.intent == "joke"
    assert turn.confidence == 0.7


def test_parse_turn_allows_reaction_only_action() -> None:
    client = LLMClient()
    turn = client._parse_turn(
        '{"reply":"","reactions":["💀"],"media":{"type":"none"},'
        '"intent":"media_reaction","confidence":0.9}'
    )
    assert turn.reply == ""
    assert turn.reactions == ("💀",)
    assert turn.intent == "media_reaction"


def test_parse_turn_falls_back_when_no_action_exists() -> None:
    client = LLMClient()
    turn = client._parse_turn('{"reply":"","reactions":[],"media":{"type":"none"}}')
    assert turn.reply
    assert turn.media.kind == "none"
    assert turn.reactions == ()


def test_json_extractor_ignores_trailing_objects() -> None:
    client = LLMClient()
    text = '{"reply":"first","media":{"type":"none"}} {"reply":"second"}'
    assert client._extract_json_object(text) == '{"reply":"first","media":{"type":"none"}}'


def test_compose_user_input_keeps_media_context() -> None:
    client = LLMClient()
    media_context = "[incoming media context: treat this socially]\n- image, embed: funny.gif"
    assert client._compose_user_input("", media_context) == media_context
    assert client._compose_user_input("look", media_context) == f"look\n{media_context}"


def test_generation_input_warns_against_recent_repetition() -> None:
    client = LLMClient()
    history = [
        {"role": "assistant", "content": "same dry roast again"},
        {"role": "user", "content": "lol"},
        {"role": "assistant", "content": "same rhythm different hat"},
    ]
    prompt = client._compose_generation_input("new message", history)
    assert "recent assistant wording to avoid repeating" in prompt
    assert "same rhythm different hat" in prompt
    assert "same dry roast again" in prompt


def test_memory_context_includes_self_reflection_lessons() -> None:
    client = LLMClient()
    context = client._memory_context("remembered thing", "- vary reactions more")
    assert "remembered thing" in context
    assert "Recent self-reflection lessons" in context
    assert "vary reactions more" in context


async def test_retry_if_unstructured_uses_valid_json_retry(monkeypatch: Any) -> None:
    client = LLMClient()
    first = client._parse_turn("reply: leaked label media: none")

    async def fake_generate(*_args: Any, **_kwargs: Any) -> str:
        return '{"reply":"clean now","reactions":[],"media":{"type":"none"}}'

    monkeypatch.setattr(client, "_generate", fake_generate)
    turn = await client._retry_if_unstructured(first, "system", [], "user", "hi")
    assert turn.reply == "clean now"
    assert turn.parse_status == "json"


async def test_retry_if_unstructured_keeps_first_when_retry_fails(monkeypatch: Any) -> None:
    client = LLMClient()
    first = client._parse_turn("reply: keep this media: none")

    async def fake_generate(*_args: Any, **_kwargs: Any) -> str:
        return "still not json"

    monkeypatch.setattr(client, "_generate", fake_generate)
    turn = await client._retry_if_unstructured(first, "system", [], "user", "hi")
    assert turn.reply == "keep this"
    assert turn.parse_status == "labeled"


async def test_retry_if_unstructured_disables_tools_and_requires_json(monkeypatch: Any) -> None:
    client = LLMClient()
    first = client._parse_turn("reply: leaked label media: none")
    seen: dict[str, Any] = {}

    async def capture_generate(*_args: Any, **kwargs: Any) -> str:
        seen.update(kwargs)
        return '{"reply":"clean now","reactions":[],"media":{"type":"none"}}'

    monkeypatch.setattr(client, "_generate", capture_generate)
    await client._retry_if_unstructured(first, "system", [], "user", "hi")
    assert seen["use_tools"] is False
    assert seen["require_json"] is True


def test_gif_requests_skip_web_search_tools() -> None:
    client = LLMClient()
    assert client._should_use_tools("send a gif of watch me whip") is False
    assert client._should_use_tools("what is the score of argentina vs egypt") is True


def test_gif_request_forces_media_when_model_forgets() -> None:
    client = LLMClient()
    turn = client._parse_turn(
        '{"schema_version":"mika_turn.v2","reply":"bet","reactions":[],"media":{"type":"none"},'
        '"intent":"chat","confidence":0.7}'
    )
    forced = client._force_requested_media(turn, "send a gif of watch me whip")
    assert forced.media.kind == "gif"
    assert forced.media.query == "watch me whip"
    assert forced.intent == "media_reaction"


def test_media_gate_drops_random_gif_on_plain_question() -> None:
    client = LLMClient()
    turn = client._parse_turn(
        '{"schema_version":"mika_turn.v2","reply":"4","reactions":[],"media":{"type":"gif","query":"math"},'
        '"intent":"chat","confidence":0.7}'
    )
    gated = client._gate_media_choice(turn, "what is 2+2?")
    assert gated.media.kind == "none"


def test_media_gate_keeps_confident_social_gif() -> None:
    client = LLMClient()
    turn = client._parse_turn(
        '{"schema_version":"mika_turn.v2","reply":"","reactions":[],'
        '"media":{"type":"gif","query":"excited dance"},'
        '"intent":"hype","confidence":0.8}'
    )
    gated = client._gate_media_choice(turn, "we actually won")
    assert gated.media.kind == "gif"
    assert gated.media.query == "excited dance"
