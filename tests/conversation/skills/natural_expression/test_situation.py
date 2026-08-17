"""Situation assessment and Unicode expression semantics."""

from mika.conversation.skills.natural_expression import assess_situation, unicode_candidates


def test_serious_or_uncertain_situation_prefers_abstention() -> None:
    serious = assess_situation("we need to talk about the outage", "serious", 0.9, True)
    uncertain = assess_situation("okay", "chat", 0.25, False)

    assert serious.emoji_mode == "avoid"
    assert uncertain.emoji_mode == "avoid"
    assert unicode_candidates(serious) == ()


def test_social_intents_map_to_distinct_semantic_families() -> None:
    joke = assess_situation("lmao that failed", "joke", 0.9, True)
    comfort = assess_situation("today was rough", "comfort", 0.9, True)
    hype = assess_situation("we actually won", "hype", 0.9, True)

    assert joke.families[0] == "amusement"
    assert comfort.families[0] == "support"
    assert hype.families[0] == "celebration"
    assert {item.family for item in unicode_candidates(joke)} == {"amusement"}


def test_catalog_has_broad_semantics_without_forcing_usage() -> None:
    situation = assess_situation("what do you think?", "question", 0.8, True)
    candidates = unicode_candidates(situation)

    assert situation.emoji_mode == "optional"
    assert candidates
    assert all(item.kind == "unicode" for item in candidates)
    assert all(item.confidence < 1.0 for item in candidates)
