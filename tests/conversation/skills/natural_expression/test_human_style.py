"""Aggregate human-style analysis and bounded profile blending."""

import sqlite3

from mika.conversation.skills.natural_expression.human_style import (
    HumanStyleProfile,
    analyze_messages,
    blend_profiles,
    load_archive_profiles,
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


def test_archive_loader_keeps_only_aggregate_profiles(tmp_path) -> None:
    path = tmp_path / "archive.sqlite"
    con = sqlite3.connect(path)
    con.execute("create table messages (role text, content text, channel_id text, author_id text)")
    con.executemany(
        "insert into messages values ('user', ?, ?, ?)",
        [("hi", "c1", "u1"), ("no way 😭", "c1", "u1"), ("longer message", "c2", "u2")],
    )
    con.commit()
    con.close()

    profiles = load_archive_profiles(path)

    assert profiles.server.sample_count == 3
    assert profiles.channels["c1"].sample_count == 2
    assert profiles.people["u1"].sample_count == 2
