"""LLM client output parsing guards."""

from __future__ import annotations

from mika.ai.llm.client import LLMClient


def test_parse_turn_strips_labeled_output_leak() -> None:
    client = LLMClient()
    turn = client._parse_turn(
        "ugh tell me about it, the company really ruins it  "
        "reply: exactly, the pasta is a 10 but night is questionable media: none"
    )
    assert turn.reply == "exactly, the pasta is a 10 but night is questionable"
    assert turn.media.kind == "none"


def test_parse_turn_accepts_json() -> None:
    client = LLMClient()
    turn = client._parse_turn(
        '{"reply":"night is fighting the flag allegations again",'
        '"reactions":["💀"],"media":{"type":"none","query":null}}'
    )
    assert turn.reply == "night is fighting the flag allegations again"
    assert turn.reactions == ("💀",)


def test_compose_user_input_keeps_media_context() -> None:
    client = LLMClient()
    media_context = "[incoming media context: treat this socially]\n- image, embed: funny.gif"
    assert client._compose_user_input("", media_context) == media_context
    assert client._compose_user_input("look", media_context) == f"look\n{media_context}"
