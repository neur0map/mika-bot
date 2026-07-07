"""Golden turn fixtures for social chat behavior contracts."""

from __future__ import annotations

from mika.ai.llm.client import LLMClient


def test_golden_sarcasm_turn_contract() -> None:
    turn = LLMClient()._parse_turn(
        '{"schema_version":"mika_turn.v2","reply":"bold strategy. terrible, but bold.",'
        '"reactions":["💀"],"media":{"type":"none","query":null},'
        '"intent":"sarcasm","confidence":0.88}'
    )
    assert turn.reply == "bold strategy. terrible, but bold."
    assert turn.reactions == ("💀",)
    assert turn.intent == "sarcasm"


def test_golden_flirt_turn_contract() -> None:
    turn = LLMClient()._parse_turn(
        '{"schema_version":"mika_turn.v2","reply":"careful, that almost sounded charming.",'
        '"reactions":["👀"],"media":{"type":"none","query":null},'
        '"intent":"flirt","confidence":0.76}'
    )
    assert turn.reply == "careful, that almost sounded charming."
    assert turn.reactions == ("👀",)
    assert turn.intent == "flirt"


def test_golden_media_reaction_contract() -> None:
    turn = LLMClient()._parse_turn(
        '{"schema_version":"mika_turn.v2","reply":"","reactions":["😂"],'
        '"media":{"type":"gif","query":"laughing shocked reaction"},'
        '"intent":"media_reaction","confidence":0.91}'
    )
    assert turn.reply == ""
    assert turn.reactions == ("😂",)
    assert turn.media.kind == "gif"
    assert turn.media.query == "laughing shocked reaction"
    assert turn.intent == "media_reaction"
