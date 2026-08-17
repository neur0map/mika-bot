"""Deterministic relationship-memory turn-relation behavior."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from mika.conversation.relationships import RelationDecision, classify_relation


def test_explicit_correction_outranks_other_turn_signals() -> None:
    """A direct correction must retain the current relationship context."""
    decision = classify_relation(
        "No, I meant the staging database, not production.",
        "How should I rotate the production database credentials?",
        "Start by scheduling a maintenance window.",
        45,
    )

    assert decision.relation == "correction"
    assert 0.9 <= decision.confidence <= 1.0
    assert "correction_phrase" in decision.signals


def test_explicit_topic_end_closes_the_current_topic() -> None:
    """An unambiguous close request must not be treated as a new topic."""
    decision = classify_relation(
        "Let's leave this topic here.",
        "Can you explain how the cache invalidation works?",
        "The cache uses a short time-to-live.",
        20,
    )

    assert decision.relation == "topic_end"
    assert 0.9 <= decision.confidence <= 1.0
    assert "topic_end_phrase" in decision.signals


def test_referential_reply_is_a_follow_up() -> None:
    """A reply containing a reference continues the preceding turn."""
    decision = classify_relation(
        "What about that second option?",
        "Should I use Redis or Postgres for this queue?",
        "Redis is simpler, while Postgres reduces infrastructure.",
        90,
        replies_to_message=True,
    )

    assert decision.relation == "follow_up"
    assert 0.8 <= decision.confidence <= 1.0
    assert {"reply_reference", "reference_signal"} <= set(decision.signals)


def test_explicit_unrelated_topic_starts_a_new_topic() -> None:
    """A stated topic switch with no shared terms starts a new topic."""
    decision = classify_relation(
        "Changing topics: what is a good sourdough starter schedule?",
        "Why is the PostgreSQL migration locking the table?",
        "The lock is waiting for an active transaction.",
        600,
    )

    assert decision.relation == "new_topic"
    assert 0.8 <= decision.confidence <= 1.0
    assert {"topic_shift_phrase", "no_token_overlap"} <= set(decision.signals)


def test_explicit_topic_shift_outranks_reply_reference() -> None:
    """An explicit topic shift must override reply structure and reference wording."""
    decision = classify_relation(
        "New topic: what about sourdough?",
        "Why is the PostgreSQL migration locking the table?",
        "The lock is waiting for an active transaction.",
        60,
        replies_to_message=True,
    )

    assert decision.relation == "new_topic"
    assert "topic_shift_phrase" in decision.signals


def test_memory_probe_requests_evidence_context() -> None:
    """A request to recall a past exchange is a memory probe."""
    decision = classify_relation(
        "Do you remember what I said about my preferred editor?",
        "I use Neovim for most of my work.",
        "That makes sense for your workflow.",
        86_400,
    )

    assert decision.relation == "memory_probe"
    assert 0.8 <= decision.confidence <= 1.0
    assert "memory_probe_phrase" in decision.signals


def test_ambiguous_short_message_defaults_to_follow_up() -> None:
    """An underspecified short turn must preserve continuity by default."""
    decision = classify_relation("Okay?", "I can suggest a few deployment options.", "Sure.", 300)

    assert decision.relation == "follow_up"
    assert 0.0 <= decision.confidence <= 1.0
    assert "default_follow_up" in decision.signals


def test_relation_decision_is_immutable() -> None:
    """Shared classifier output cannot change after a decision is made."""
    decision = RelationDecision("follow_up", 0.5, "fallback")

    with pytest.raises(FrozenInstanceError):
        decision.confidence = 1.0
