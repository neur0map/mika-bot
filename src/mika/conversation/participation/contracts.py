"""Typed participation decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ParticipationMode = Literal["reply", "react", "media", "observe"]


@dataclass(frozen=True, slots=True)
class ParticipationDecision:
    """A bounded pre-generation social participation candidate."""

    mode: ParticipationMode
    reason: str
    confidence: float
