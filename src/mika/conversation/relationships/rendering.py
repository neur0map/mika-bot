"""Budgeted whole-tier rendering for ranked relationship memories."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from mika.conversation.context.contracts import MemoryCandidate
from mika.conversation.relationships.contracts import RelationDecision

_TIER_ORDER = ("index", "overview", "evidence")
_SECTION_HEADER = "Relationship memory:"
_ENTRY_PREFIX = "-"


@dataclass(frozen=True, slots=True)
class RenderedMemory:
    """Bounded context and auditable selection decisions."""

    text: str
    selected_ids: tuple[str, ...]
    selected_tiers: Mapping[str, str]
    rejection_reasons: Mapping[str, str]
    estimated_token_cost: int


class TieredMemoryRenderer:
    """Allocate safe complete representations without slicing entries."""

    def __init__(self, *, token_budget: int = 700, per_entry_token_cap: int = 180) -> None:
        self._token_budget = max(0, token_budget)
        self._per_entry_cap = max(0, per_entry_token_cap)

    def render(
        self,
        candidates: Sequence[MemoryCandidate],
        relation: RelationDecision,
    ) -> RenderedMemory:
        """Render anchors first, then breadth before depth for other memories."""
        selected: dict[str, tuple[MemoryCandidate, str, str, int]] = {}
        reasons: dict[str, str] = {}
        header_cost = estimate_tokens(_SECTION_HEADER)
        remaining = max(0, self._token_budget - header_cost)
        anchors = [item for item in candidates if item.evidence_class in {"correction", "explicit"}]
        others = [item for item in candidates if item not in anchors]
        remaining = self._select_anchors(anchors, relation, selected, reasons, remaining)
        remaining = self._select_indexes(others, selected, reasons, remaining)
        self._deepen(others, relation, selected, reasons, remaining)

        ordered = [
            selected[item.candidate_id]
            for item in anchors + others
            if item.candidate_id in selected
        ]
        lines = [f"{_ENTRY_PREFIX} {text}" for _, _, text, _ in ordered]
        text = f"{_SECTION_HEADER}\n" + "\n".join(lines) if lines else ""
        tiers = {candidate.candidate_id: tier for candidate, tier, _, _ in ordered}
        total = header_cost + sum(cost for _, _, _, cost in ordered) if ordered else 0
        return RenderedMemory(
            text,
            tuple(candidate.candidate_id for candidate, _, _, _ in ordered),
            tiers,
            reasons,
            total,
        )

    def _select_anchors(
        self,
        candidates: Sequence[MemoryCandidate],
        relation: RelationDecision,
        selected: dict[str, tuple[MemoryCandidate, str, str, int]],
        reasons: dict[str, str],
        remaining: int,
    ) -> int:
        for candidate in candidates:
            choice, reason = self._best_fit(candidate, relation, remaining)
            if choice is None:
                reasons[candidate.candidate_id] = reason
                continue
            tier, text, cost = choice
            selected[candidate.candidate_id] = (candidate, tier, text, cost)
            remaining -= cost
            if reason:
                reasons[candidate.candidate_id] = reason
        return remaining

    def _select_indexes(
        self,
        candidates: Sequence[MemoryCandidate],
        selected: dict[str, tuple[MemoryCandidate, str, str, int]],
        reasons: dict[str, str],
        remaining: int,
    ) -> int:
        for candidate in candidates:
            index_text = candidate.index_text.strip()
            cost = estimate_tokens(index_text)
            reason = self._index_rejection(index_text, cost, remaining)
            if reason:
                reasons[candidate.candidate_id] = reason
                continue
            framed_cost = _framed_cost(index_text)
            selected[candidate.candidate_id] = (candidate, "index", index_text, framed_cost)
            remaining -= framed_cost
        return remaining

    def _deepen(
        self,
        candidates: Sequence[MemoryCandidate],
        relation: RelationDecision,
        selected: dict[str, tuple[MemoryCandidate, str, str, int]],
        reasons: dict[str, str],
        remaining: int,
    ) -> None:
        for candidate in candidates:
            current = selected.get(candidate.candidate_id)
            if current is None:
                continue
            upgraded, reason = self._upgrade(candidate, current, relation, remaining)
            if upgraded is not None:
                remaining -= upgraded[3] - current[3]
                selected[candidate.candidate_id] = upgraded
            if reason:
                reasons[candidate.candidate_id] = reason

    def _index_rejection(self, text: str, cost: int, remaining: int) -> str:
        if not text:
            return "empty_index"
        if cost > self._per_entry_cap:
            return "per_entry_cap:index"
        if _framed_cost(text) > remaining:
            return "token_budget:index"
        return ""

    def _best_fit(
        self,
        candidate: MemoryCandidate,
        relation: RelationDecision,
        remaining: int,
    ) -> tuple[tuple[str, str, int] | None, str]:
        desired = _desired_tier(candidate, relation)
        representations = _representations(candidate)
        desired_index = _TIER_ORDER.index(desired)
        cap_blocked = False
        for tier in reversed(_TIER_ORDER[: desired_index + 1]):
            text = representations.get(tier)
            if not text:
                continue
            cost = estimate_tokens(text)
            if cost > self._per_entry_cap:
                cap_blocked = True
                continue
            framed_cost = _framed_cost(text)
            if framed_cost > remaining:
                continue
            if tier == desired:
                return (tier, text, framed_cost), ""
            constraint = "per_entry_cap" if cap_blocked else "token_budget"
            return (tier, text, framed_cost), f"{constraint}:{desired}->{tier}"
        constraint = "per_entry_cap" if cap_blocked else "token_budget"
        return None, f"{constraint}:{desired}"

    def _upgrade(
        self,
        candidate: MemoryCandidate,
        current: tuple[MemoryCandidate, str, str, int],
        relation: RelationDecision,
        remaining: int,
    ) -> tuple[tuple[MemoryCandidate, str, str, int] | None, str]:
        desired = _desired_tier(candidate, relation)
        if desired == current[1]:
            return None, ""
        representations = _representations(candidate)
        current_index = _TIER_ORDER.index(current[1])
        desired_index = _TIER_ORDER.index(desired)
        constraint = ""
        for tier in reversed(_TIER_ORDER[current_index + 1 : desired_index + 1]):
            text = representations.get(tier)
            if not text:
                continue
            cost = estimate_tokens(text)
            if cost > self._per_entry_cap:
                constraint = "per_entry_cap"
                continue
            framed_cost = _framed_cost(text)
            if framed_cost - current[3] > remaining:
                constraint = "token_budget"
                continue
            reason = f"{constraint}:{desired}->{tier}" if constraint else ""
            return (candidate, tier, text, framed_cost), reason
        reason = f"{constraint}:{desired}->{current[1]}" if constraint else ""
        return None, reason


def estimate_tokens(text: str) -> int:
    """Return a deterministic conservative word-token estimate."""
    return len(text.split())


def _framed_cost(text: str) -> int:
    return estimate_tokens(f"{_ENTRY_PREFIX} {text}")


def _desired_tier(candidate: MemoryCandidate, relation: RelationDecision) -> str:
    if relation.relation in {"memory_probe", "correction"} and candidate.evidence_text:
        return "evidence"
    if candidate.overview_text:
        return "overview"
    return "index"


def _representations(candidate: MemoryCandidate) -> dict[str, str]:
    values = {
        "index": candidate.index_text.strip(),
        "overview": (candidate.overview_text or "").strip(),
        "evidence": (candidate.evidence_text or "").strip(),
    }
    return {tier: text for tier, text in values.items() if text}
