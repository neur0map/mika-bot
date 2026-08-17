"""Immutable, layered relationship profiles derived from active claims."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProfileEntry:
    """One compact profile statement with its source-claim identities."""

    key: str
    value: str
    claim_ids: tuple[str, ...]

    def render(self) -> str:
        """Return the compact user-facing portion of this entry."""
        return f"{self.key}: {self.value}"


@dataclass(frozen=True, slots=True)
class RelationshipProfile:
    """A versioned, deterministic summary of one person's relationship evidence."""

    subject_user_id: str
    version: int
    posture: tuple[ProfileEntry, ...] = ()
    expression: tuple[ProfileEntry, ...] = ()
    interests: tuple[ProfileEntry, ...] = ()
    care_patterns: tuple[ProfileEntry, ...] = ()
    conflict_repair: tuple[ProfileEntry, ...] = ()
    anchors: tuple[ProfileEntry, ...] = ()

    @property
    def index_text(self) -> str:
        """Return a short deterministic index representation."""
        return " | ".join(entry.render() for entry in self.entries)

    @property
    def overview_text(self) -> str:
        """Render a compact structured overview without exposing source identifiers."""
        sections = (
            ("Posture", self.posture),
            ("Expression", self.expression),
            ("Interests", self.interests),
            ("Care patterns", self.care_patterns),
            ("Conflict and repair", self.conflict_repair),
            ("Anchors", self.anchors),
        )
        return "\n".join(
            f"{title}: " + "; ".join(entry.render() for entry in items)
            for title, items in sections
            if items
        )

    @property
    def entries(self) -> tuple[ProfileEntry, ...]:
        """Return all layers in stable rendering order."""
        return (
            *self.posture,
            *self.expression,
            *self.interests,
            *self.care_patterns,
            *self.conflict_repair,
            *self.anchors,
        )

    def canonical_content(self) -> tuple[tuple[ProfileEntry, ...], ...]:
        """Return version-independent content for no-op detection."""
        return (
            self.posture,
            self.expression,
            self.interests,
            self.care_patterns,
            self.conflict_repair,
            self.anchors,
        )
