"""Human-distribution-aware expression decisions."""

from mika.conversation.skills.natural_expression import EmojiProfile
from mika.conversation.skills.natural_expression.human_style import HumanStyleProfile
from mika.conversation.skills.natural_expression.skill import NaturalExpressionSkill

_SERVER = HumanStyleProfile(12031, 5, 0.044, 0.0014, 0.0276, 0.53, 0.025)


def test_ordinary_chat_uses_human_emoji_prior_and_abstains() -> None:
    skill = NaturalExpressionSkill(_SERVER)

    guidance = skill.guide("c", "okay", "chat", 0.7, mentioned=False)

    assert guidance.situation.emoji_mode == "optional"
    assert guidance.candidates == ()
    assert guidance.target_words == 5
    assert guidance.avoid_dash


def test_strong_social_context_can_offer_bounded_candidate() -> None:
    skill = NaturalExpressionSkill(_SERVER)
    custom = EmojiProfile(
        "<:side_eye:123>",
        "skepticism",
        "skeptical reaction",
        0.91,
        kind="guild",
        guild_id="g",
    )

    guidance = skill.guide("c", "be serious", "sarcasm", 0.94, mentioned=True, profiles=(custom,))

    assert guidance.candidates[0].profile == custom


def test_validator_removes_unjustified_emoji_and_normalizes_generated_dash() -> None:
    skill = NaturalExpressionSkill(_SERVER)
    guidance = skill.guide("c", "okay", "chat", 0.7, mentioned=False)

    assert skill.validate("yeah — sure 😏", guidance) == "yeah, sure"


def test_validator_collapses_polished_multi_sentence_cadence() -> None:
    skill = NaturalExpressionSkill(_SERVER)
    guidance = skill.guide("c", "okay", "chat", 0.7, mentioned=False)

    assert (
        skill.validate("Rude. Unfortunately accurate.", guidance) == "Rude, unfortunately accurate."
    )
    assert skill.validate("Yes. It happened.", guidance) == "Yes, it happened."
