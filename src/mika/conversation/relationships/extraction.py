"""Closed-pattern, source-traceable relationship-evidence extraction."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from mika.conversation.relationships.contracts import EvidenceClass, RelationDecision

_MAX_VALUE_LENGTH = 120
_MAX_KEY_LENGTH = 64
_REPEATED_EMOJI_MINIMUM = 2
_PREFERENCE = re.compile(
    r"\b(?:i\s+(?:really\s+)?(?:prefer|like|love)|my\s+favorite\s+is)\s+(?P<value>[^.,!?;]+)",
    re.IGNORECASE,
)
_NAME = re.compile(r"\bmy\s+name\s+is\s+(?P<value>[^.,!?;]+)", re.IGNORECASE)
_ADDRESS_BOUNDARY = re.compile(
    r"\b(?:please\s+)?don(?:'|\u2019)t\s+call\s+me\s+(?P<value>[^.,!?;]+)",
    re.IGNORECASE,
)
_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF]")
_SENSITIVE_CONTENT = re.compile(
    r"\b(?:diagnos(?:ed|is)|adhd|autis(?:m|tic)|depress(?:ed|ion)|bipolar|"
    r"schizophren(?:ia|ic)|disabled|gay|lesbian|bisexual|transgender|"
    r"muslim|christian|jewish|hindu|race|ethnicity)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class EvidenceProposal:
    """One bounded claim candidate tied to the exact source message."""

    kind: str
    key: str
    value: str
    evidence_class: EvidenceClass
    confidence: float
    source_message_id: str
    source_timestamp: datetime
    reason: str


def extract_deterministic_evidence(
    text: str,
    *,
    source_message_id: str,
    source_timestamp: datetime,
    relation: RelationDecision,
) -> tuple[EvidenceProposal, ...]:
    """Return only auditable, non-sensitive evidence from one user message."""
    if _SENSITIVE_CONTENT.search(text):
        return ()

    evidence_class = _evidence_class(relation)
    proposals = [
        *_explicit_proposals(text, source_message_id, source_timestamp, evidence_class),
        *_expression_proposals(text, source_message_id, source_timestamp),
    ]
    return tuple(proposals)


def _explicit_proposals(
    text: str,
    source_message_id: str,
    source_timestamp: datetime,
    evidence_class: EvidenceClass,
) -> tuple[EvidenceProposal, ...]:
    proposals: list[EvidenceProposal] = []
    preference = _PREFERENCE.search(text)
    if preference is not None:
        value = _bounded_value(preference.group("value"))
        if value:
            proposals.append(
                _proposal(
                    "preference",
                    _normalized_key("preference", value),
                    value.lower(),
                    evidence_class,
                    source_message_id,
                    source_timestamp,
                    "direct_preference",
                )
            )

    name = _NAME.search(text)
    if name is not None:
        value = _bounded_value(name.group("value"))
        if value:
            proposals.append(
                _proposal(
                    "identity",
                    "identity:name",
                    value,
                    evidence_class,
                    source_message_id,
                    source_timestamp,
                    "direct_name",
                )
            )

    boundary = _ADDRESS_BOUNDARY.search(text)
    if boundary is not None:
        value = _bounded_value(boundary.group("value"))
        if value:
            proposals.append(
                _proposal(
                    "boundary",
                    _normalized_key("address", value),
                    "avoid",
                    evidence_class,
                    source_message_id,
                    source_timestamp,
                    "direct_address_boundary",
                )
            )
    return tuple(proposals)


def _expression_proposals(
    text: str,
    source_message_id: str,
    source_timestamp: datetime,
) -> tuple[EvidenceProposal, ...]:
    counts = Counter(_EMOJI.findall(text))
    return tuple(
        _proposal(
            "expression",
            f"expression:emoji:{emoji}",
            f"count:{count}",
            "repeated_behavior",
            source_message_id,
            source_timestamp,
            "repeated_emoji",
        )
        for emoji, count in counts.items()
        if count >= _REPEATED_EMOJI_MINIMUM
    )


def _evidence_class(relation: RelationDecision) -> EvidenceClass:
    """Give direct statements correction precedence only in correction turns."""
    if relation.relation == "correction":
        return "correction"
    return "explicit"


def _proposal(
    kind: str,
    key: str,
    value: str,
    evidence_class: EvidenceClass,
    source_message_id: str,
    source_timestamp: datetime,
    reason: str,
) -> EvidenceProposal:
    """Build one proposal with confidence determined by its closed pattern."""
    confidence = 0.98 if evidence_class == "correction" else 0.95
    if evidence_class == "repeated_behavior":
        confidence = 0.5
    return EvidenceProposal(
        kind=kind,
        key=key,
        value=value[:_MAX_VALUE_LENGTH],
        evidence_class=evidence_class,
        confidence=confidence,
        source_message_id=source_message_id,
        source_timestamp=source_timestamp,
        reason=reason,
    )


def _bounded_value(value: str) -> str:
    """Normalize whitespace and cap untrusted message content."""
    return " ".join(value.split()).strip()[:_MAX_VALUE_LENGTH]


def _normalized_key(prefix: str, value: str) -> str:
    """Create a compact stable key without retaining arbitrary punctuation."""
    remaining = _MAX_KEY_LENGTH - len(prefix) - 1
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return f"{prefix}:{normalized[:remaining].strip('-')}"
