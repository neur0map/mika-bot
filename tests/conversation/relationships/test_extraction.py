"""Conservative deterministic relationship-evidence extraction."""

from __future__ import annotations

from datetime import UTC, datetime

from mika.conversation.relationships import RelationDecision, RelationKind
from mika.conversation.relationships.extraction import (
    EvidenceProposal,
    extract_deterministic_evidence,
)

SOURCE_TIME = datetime(2026, 8, 17, 10, tzinfo=UTC)


def extract(text: str, relation: RelationKind = "new_topic") -> tuple[EvidenceProposal, ...]:
    """Extract proposals with stable source metadata."""
    return extract_deterministic_evidence(
        text,
        source_message_id="message-42",
        source_timestamp=SOURCE_TIME,
        relation=RelationDecision(relation, 0.95, "test"),
    )


def test_extracts_an_explicit_preference_with_traceable_source() -> None:
    """A direct preference is safe, normalized evidence."""
    proposals = extract("I prefer iced tea.")

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.kind == "preference"
    assert proposal.key == "preference:iced-tea"
    assert proposal.value == "iced tea"
    assert proposal.evidence_class == "explicit"
    assert proposal.source_message_id == "message-42"
    assert proposal.source_timestamp == SOURCE_TIME


def test_extracts_an_explicit_identity_fact() -> None:
    """A direct name statement is retained without extrapolation."""
    proposals = extract("My name is Ada Lovelace.")

    assert [(proposal.kind, proposal.key, proposal.value) for proposal in proposals] == [
        ("identity", "identity:name", "Ada Lovelace"),
    ]


def test_extracts_a_direct_correction_over_an_explicit_fact() -> None:
    """A correction receives its stronger evidence class."""
    proposals = extract("No, I prefer tea, not coffee.", "correction")

    assert [(proposal.key, proposal.value, proposal.evidence_class) for proposal in proposals] == [
        ("preference:tea", "tea", "correction"),
    ]


def test_extracts_a_measurable_expression_observation() -> None:
    """Repeated emoji in one source is observable without inferring emotion."""
    proposals = extract("that deploy was wild 😂😂😂")

    actual = [
        (proposal.kind, proposal.key, proposal.value, proposal.evidence_class)
        for proposal in proposals
    ]
    assert actual == [
        ("expression", "expression:emoji:😂", "count:3", "repeated_behavior"),
    ]


def test_extracts_a_non_sensitive_address_boundary() -> None:
    """A direct address preference is a bounded, auditable boundary."""
    proposals = extract("Please don't call me buddy.")

    assert [(proposal.kind, proposal.key, proposal.value) for proposal in proposals] == [
        ("boundary", "address:buddy", "avoid"),
    ]


def test_rejects_diagnoses_and_sensitive_inferences() -> None:
    """Medical and protected-attribute claims must not enter relationship memory."""
    assert extract("I was diagnosed with ADHD.") == ()
    assert extract("You seem depressed lately.") == ()
    assert extract("I am bisexual.") == ()


def test_caps_explicit_values_before_they_become_memory() -> None:
    """Direct facts stay bounded even when a message is verbose."""
    detail = "x" * 200

    proposals = extract(f"I prefer {detail}.")

    assert len(proposals) == 1
    assert len(proposals[0].value) == 120
