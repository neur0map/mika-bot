"""Structured social-turn parsing independent of provider clients."""

from __future__ import annotations

from mika.conversation.generation import TurnParser


def test_parser_accepts_strict_social_turn_json() -> None:
    turn = TurnParser().parse(
        '{"schema_version":"mika_turn.v2","reply":"bold strategy",'
        '"reactions":["💀"],"media":{"type":"none","query":null},'
        '"intent":"sarcasm","confidence":0.88}'
    )

    assert turn.reply == "bold strategy"
    assert turn.reactions == ("💀",)
    assert turn.intent == "sarcasm"
    assert turn.parse_status == "json"


def test_parser_preserves_explicit_silence_but_recovers_empty_accident() -> None:
    parser = TurnParser()

    silent = parser.parse(
        '{"reply":"","reactions":[],"media":{"type":"none"},"intent":"silence","confidence":0.9}'
    )
    accidental = parser.parse('{"reply":"","reactions":[],"media":{"type":"none"}}')

    assert silent.is_silent
    assert accidental.reply == "brain snagged. give me a second and try again."


def test_parser_limits_social_reply_and_drops_ineligible_media() -> None:
    turn = TurnParser().parse(
        '{"reply":"' + ("word " * 100) + '","reactions":[],'
        '"media":{"type":"gif","query":"math"},"intent":"chat","confidence":0.7}',
        user_input="what is 2+2?",
    )

    assert len(turn.reply) <= 180
    assert turn.media.kind == "none"
