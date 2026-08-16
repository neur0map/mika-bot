"""Conservative extraction of facts users explicitly state about themselves."""

from __future__ import annotations

import re

_FACT_PATTERNS = (
    (
        re.compile(r"\b(?:actually\s+)?my favorite ([a-z][a-z ]{1,30}) is ([^.!?\n]{1,100})", re.I),
        "favorite",
    ),
    (re.compile(r"\bmy name is ([^.!?\n]{1,80})", re.I), "name"),
    (re.compile(r"\bi (?:work as|am) an? ([^.!?\n]{1,100})", re.I), "occupation"),
    (re.compile(r"\bi (?:really )?(like|love|prefer|hate) ([^.!?\n]{1,100})", re.I), "preference"),
)
_KEY_PART = re.compile(r"[^a-z0-9]+")


def extract_explicit_facts(text: str) -> tuple[tuple[str, str], ...]:
    """Return replaceable keys only for explicit first-person statements."""
    facts: list[tuple[str, str]] = []
    for pattern, kind in _FACT_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        if kind == "favorite":
            subject = _KEY_PART.sub("_", match.group(1).strip().casefold()).strip("_")
            key, value = f"favorite_{subject}", match.group(2)
        elif kind == "preference":
            key, value = "preference", f"{match.group(1).casefold()} {match.group(2)}"
        else:
            key, value = kind, match.group(1)
        cleaned = " ".join(value.split()).strip(" ,;:-")
        if cleaned:
            facts.append((key, cleaned[:120]))
    return tuple(facts)
