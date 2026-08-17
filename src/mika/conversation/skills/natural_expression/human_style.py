"""Aggregate-only human writing profiles."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from statistics import median

_WORD = re.compile(r"[\w']+", re.UNICODE)
_EMOJI = re.compile(r"<a?:[^:>]+:\d+>|[\U0001F300-\U0001FAFF\u2600-\u27BF]")
_MIN_PERSON_SAMPLES = 30
_MULTI_SENTENCE_COUNT = 2


@dataclass(frozen=True, slots=True)
class HumanStyleProfile:
    """Non-identifying aggregate style statistics."""

    sample_count: int
    median_words: int
    emoji_rate: float
    em_dash_rate: float
    ellipsis_rate: float
    lowercase_rate: float
    multi_sentence_rate: float


@dataclass(frozen=True, slots=True)
class HumanStyleProfiles:
    """Server baseline plus bounded channel and person aggregates."""

    server: HumanStyleProfile
    channels: dict[str, HumanStyleProfile]
    people: dict[str, HumanStyleProfile]


def analyze_messages(messages: list[str]) -> HumanStyleProfile:
    """Summarize messages without retaining their content."""
    clean = [message.strip() for message in messages if message.strip()]
    if not clean:
        return HumanStyleProfile(0, 5, 0.0, 0.0, 0.0, 0.5, 0.0)
    count = len(clean)
    word_counts = [len(_WORD.findall(message)) for message in clean]
    return HumanStyleProfile(
        count,
        int(median(word_counts)),
        sum(bool(_EMOJI.search(message)) for message in clean) / count,
        sum("—" in message or "\u2013" in message for message in clean) / count,
        sum("..." in message or "…" in message for message in clean) / count,
        sum(message[:1].islower() for message in clean) / count,
        sum(
            len(re.findall(r"[.!?]+(?:\s|$)", message)) >= _MULTI_SENTENCE_COUNT
            for message in clean
        )
        / count,
    )


def blend_profiles(
    server: HumanStyleProfile,
    channel: HumanStyleProfile | None,
    person: HumanStyleProfile | None,
) -> HumanStyleProfile:
    """Blend local context while keeping server culture dominant."""
    if channel is None and (person is None or person.sample_count < _MIN_PERSON_SAMPLES):
        return server
    channel_weight = 0.2 if channel is not None else 0.0
    person_weight = (
        0.1 if person is not None and person.sample_count >= _MIN_PERSON_SAMPLES else 0.0
    )
    server_weight = 1.0 - channel_weight - person_weight
    profiles = [(server, server_weight)]
    if channel is not None:
        profiles.append((channel, channel_weight))
    if person_weight and person is not None:
        profiles.append((person, person_weight))

    def weighted(name: str) -> float:
        return sum(float(getattr(profile, name)) * weight for profile, weight in profiles)

    return HumanStyleProfile(
        sum(profile.sample_count for profile, _ in profiles),
        max(server.median_words - 1, min(server.median_words + 2, round(weighted("median_words")))),
        min(server.emoji_rate + 0.08, weighted("emoji_rate")),
        min(0.03, weighted("em_dash_rate")),
        min(server.ellipsis_rate + 0.08, weighted("ellipsis_rate")),
        weighted("lowercase_rate"),
        min(server.multi_sentence_rate + 0.08, weighted("multi_sentence_rate")),
    )


def load_archive_profiles(path: Path | None) -> HumanStyleProfiles:
    """Load aggregate human style from the local archive without retaining text."""
    fallback = HumanStyleProfile(0, 5, 0.044, 0.0014, 0.0276, 0.53, 0.025)
    if path is None or not path.is_file():
        return HumanStyleProfiles(fallback, {}, {})
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = connection.execute(
            "select content, channel_id, author_id from messages "
            "where role = 'user' and trim(content) <> ''"
        ).fetchall()
        connection.close()
    except sqlite3.Error:
        return HumanStyleProfiles(fallback, {}, {})
    channel_messages: dict[str, list[str]] = {}
    person_messages: dict[str, list[str]] = {}
    messages: list[str] = []
    for content, channel_id, author_id in rows:
        value = str(content)
        messages.append(value)
        channel_messages.setdefault(str(channel_id or ""), []).append(value)
        person_messages.setdefault(str(author_id or ""), []).append(value)
    return HumanStyleProfiles(
        analyze_messages(messages),
        {key: analyze_messages(value) for key, value in channel_messages.items() if key},
        {key: analyze_messages(value) for key, value in person_messages.items() if key},
    )
