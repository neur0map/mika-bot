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
