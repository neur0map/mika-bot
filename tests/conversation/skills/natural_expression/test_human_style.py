"""Aggregate human-style analysis and bounded profile blending."""

from mika.conversation.skills.natural_expression.human_style import (
    HumanStyleProfile,
    analyze_messages,
    blend_profiles,
)


def test_analyzer_learns_distribution_without_retaining_messages() -> None:
    profile = analyze_messages(
        ["hey", "no way 😭", "what are you doing", "fine...", "this is two. sentences."]
    )

    assert profile.sample_count == 5
    assert profile.median_words == 2
    assert profile.emoji_rate == 0.2
    assert profile.ellipsis_rate == 0.2
    assert not hasattr(profile, "messages")


def test_person_profile_is_bounded_by_server_baseline() -> None:
    server = HumanStyleProfile(1000, 5, 0.04, 0.001, 0.03, 0.5, 0.02)
    channel = HumanStyleProfile(200, 6, 0.06, 0.002, 0.04, 0.6, 0.03)
    person = HumanStyleProfile(80, 12, 0.8, 0.4, 0.5, 0.0, 0.6)

    blended = blend_profiles(server, channel, person)

    assert 5 <= blended.median_words <= 7
    assert blended.emoji_rate <= 0.12
    assert blended.em_dash_rate <= 0.03


def test_small_person_sample_does_not_change_server_profile() -> None:
    server = HumanStyleProfile(1000, 5, 0.04, 0.001, 0.03, 0.5, 0.02)
    person = HumanStyleProfile(3, 20, 1.0, 1.0, 1.0, 0.0, 1.0)

    assert blend_profiles(server, None, person) == server
