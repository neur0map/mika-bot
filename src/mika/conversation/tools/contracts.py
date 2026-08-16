"""Typed tool eligibility and execution values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ToolStatus = Literal["success", "failure", "denied"]


@dataclass(frozen=True, slots=True)
class ToolPlan:
    """Names eligible for one turn and the reason for that exposure."""

    names: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    """One bounded tool execution result."""

    name: str
    status: ToolStatus
    summary: str
    duration_ms: float
    reason: str | None = None
