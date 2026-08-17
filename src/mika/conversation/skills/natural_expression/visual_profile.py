"""Pluggable visual evidence for custom emoji."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VisualEvidence:
    """Inspectable evidence produced by an emoji visual profiler."""

    description: str
    family: str
    confidence: float
    animated: bool


class VisualProfiler:
    """Provide a conservative fallback until local image profiling is configured."""

    def describe(self, name: str, *, animated: bool) -> VisualEvidence:
        """Turn a mutable Discord name into weak evidence, never ground truth."""
        words = re.sub(r"[_-]+", " ", name).strip().lower() or "custom emoji"
        return VisualEvidence(words, "unknown", 0.25, animated)
