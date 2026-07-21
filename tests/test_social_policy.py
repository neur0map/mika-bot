"""Social action cooldown and direct-question policy contracts."""

from __future__ import annotations

from mika.ai.llm.social_policy import SocialActionPolicy, SocialContext
from mika.ai.llm.turn import MediaChoice, MikaTurn


def _context(*, direct_question: bool = False) -> SocialContext:
    return SocialContext(
        channel_id="channel",
        mentioned=direct_question,
        direct_question=direct_question,
        inbound_media_count=0,
    )


def test_direct_question_overrides_silent_turn() -> None:
    decision = SocialActionPolicy().apply(
        MikaTurn(reply="", intent="silence"), _context(direct_question=True), now=1
    )

    assert decision.turn.reply
    assert decision.turn.intent == "question"
    assert decision.suppression_reason == "direct_question_override"


def test_media_cooldown_preserves_text_reply() -> None:
    policy = SocialActionPolicy()
    turn = MikaTurn(reply="huge", media=MediaChoice("gif", "celebration"), intent="hype")
    policy.record_visible_actions(turn, _context(), now=1)

    decision = policy.apply(turn, _context(), now=2)

    assert decision.turn.reply == "huge"
    assert decision.turn.media.kind == "none"
    assert decision.suppression_reason == "media_cooldown"


def test_reaction_cooldown_does_not_block_media() -> None:
    policy = SocialActionPolicy()
    first = MikaTurn(reply="", reactions=("😂",), intent="joke")
    policy.record_visible_actions(first, _context(), now=1)
    turn = MikaTurn(reply="", reactions=("😂",), media=MediaChoice("gif", "laugh"), intent="joke")

    decision = policy.apply(turn, _context(), now=2)

    assert decision.turn.reactions == ()
    assert decision.turn.media.kind == "gif"
    assert decision.suppression_reason == "reaction_cooldown"
