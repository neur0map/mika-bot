"""Deterministic relation classification before relationship-memory retrieval."""

from __future__ import annotations

import re

from mika.conversation.relationships.contracts import RelationDecision, RelationKind

_CORRECTION_PATTERN = re.compile(
    r"^\s*(?:no(?:pe)?[,.]?|actually[,.]?|incorrect[,.]?|wrong[,.]?|i meant\b|"
    r"that(?:'s| is) not)\b",
    re.IGNORECASE,
)
_TOPIC_END_PATTERN = re.compile(
    r"\b(?:let'?s (?:leave|end|stop) (?:this|the) topic|that'?s all(?: for now)?|"
    r"drop (?:this|it)|never mind)\b",
    re.IGNORECASE,
)
_MEMORY_PROBE_PATTERN = re.compile(
    r"\b(?:do you remember|remember what i said|what did i (?:say|tell you)|you mentioned)\b",
    re.IGNORECASE,
)
_TOPIC_SHIFT_PATTERN = re.compile(
    r"\b(?:changing (?:the )?topics?|new topic|different question|moving on)\b",
    re.IGNORECASE,
)
_SOCIAL_CHECK_IN_PATTERN = re.compile(
    r"\b(?:how are you|how have you been|hope you(?:'re| are) doing well)\b",
    re.IGNORECASE,
)
_REFERENCE_PATTERN = re.compile(
    r"\b(?:this|that|these|those|it|they|them|there|then|second option|what about)\b",
    re.IGNORECASE,
)
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?", re.IGNORECASE)
_STOP_TOKENS = frozenset(
    {
        "a",
        "about",
        "an",
        "and",
        "are",
        "be",
        "by",
        "for",
        "how",
        "i",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "this",
        "to",
        "what",
        "with",
        "you",
    }
)
_NEW_TOPIC_GAP_SECONDS = 7_200


def classify_relation(
    current_text: str,
    previous_user_text: str | None = None,
    previous_assistant_text: str | None = None,
    elapsed_seconds: float = 0.0,
    *,
    replies_to_message: bool = False,
) -> RelationDecision:
    """Return a conservative closed relation label for one incoming user message."""
    text = current_text.strip()
    explicit = _explicit_relation(text)
    if explicit is not None:
        return explicit
    referential = _referential_follow_up(text, replies_to_message)
    if referential is not None:
        return referential

    return _continuity_relation(
        text,
        previous_user_text,
        previous_assistant_text,
        elapsed_seconds,
    )


def _explicit_relation(text: str) -> RelationDecision | None:
    """Return a relation selected by an unambiguous lexical phrase."""
    if _CORRECTION_PATTERN.search(text):
        return _decision("correction", 0.95, "explicit correction", "correction_phrase")
    if _TOPIC_END_PATTERN.search(text):
        return _decision("topic_end", 0.95, "explicit topic end", "topic_end_phrase")
    if _MEMORY_PROBE_PATTERN.search(text):
        return _decision("memory_probe", 0.9, "explicit memory request", "memory_probe_phrase")
    if _SOCIAL_CHECK_IN_PATTERN.search(text):
        return _decision("social_check_in", 0.85, "social check-in", "social_check_in_phrase")
    return None


def _referential_follow_up(text: str, replies_to_message: bool) -> RelationDecision | None:
    """Return a follow-up when reply structure or wording preserves context."""
    signals: list[str] = []
    if replies_to_message:
        signals.append("reply_reference")
    if _REFERENCE_PATTERN.search(text):
        signals.append("reference_signal")
    if signals:
        confidence = 0.9 if replies_to_message else 0.8
        return RelationDecision("follow_up", confidence, "referential follow-up", tuple(signals))
    return None


def _continuity_relation(
    text: str,
    previous_user_text: str | None,
    previous_assistant_text: str | None,
    elapsed_seconds: float,
) -> RelationDecision:
    """Use lexical overlap and elapsed time only after direct cues are absent."""
    overlap = _token_overlap(text, previous_user_text, previous_assistant_text)
    if _TOPIC_SHIFT_PATTERN.search(text):
        topic_signals = ["topic_shift_phrase"]
        if not overlap:
            topic_signals.append("no_token_overlap")
        return RelationDecision("new_topic", 0.9, "explicit topic change", tuple(topic_signals))
    if overlap:
        return _decision("follow_up", 0.75, "shared conversation terms", "token_overlap")
    if elapsed_seconds >= _NEW_TOPIC_GAP_SECONDS:
        return _decision("new_topic", 0.8, "long gap without references", "elapsed_gap")
    return _decision(
        "follow_up",
        0.5,
        "ambiguous message preserves continuity",
        "default_follow_up",
    )


def _decision(
    relation: RelationKind,
    confidence: float,
    reason: str,
    signal: str,
) -> RelationDecision:
    """Build a classifier decision from one decisive lexical signal."""
    return RelationDecision(relation, confidence, reason, (signal,))


def _token_overlap(current_text: str, *previous_texts: str | None) -> bool:
    """Return whether meaningful tokens recur in the recent conversation."""
    current_tokens = _meaningful_tokens(current_text)
    previous_tokens = set().union(*(_meaningful_tokens(text) for text in previous_texts if text))
    return bool(current_tokens & previous_tokens)


def _meaningful_tokens(text: str) -> set[str]:
    """Normalize English lexical tokens while excluding non-discriminating words."""
    return {
        token.lower() for token in _TOKEN_PATTERN.findall(text) if token.lower() not in _STOP_TOKENS
    }
