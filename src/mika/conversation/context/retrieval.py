"""Bounded lexical retrieval with same-user and same-channel affinity."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from mika.conversation.contracts import ConversationEnvelope

_TOKEN = re.compile(r"[a-z0-9']{3,}", re.I)
_CANDIDATE_LIMIT = 80


class CandidateMessage(Protocol):
    channel_id: str
    author_id: str
    author_name: str
    content: str


class SocialMemorySource(Protocol):
    async def facts(self, user_id: str, *, limit: int = 12) -> list[tuple[str, str]]: ...

    async def candidates(
        self, channel_id: str, author_id: str, *, limit: int = _CANDIDATE_LIMIT
    ) -> Sequence[CandidateMessage]: ...

    async def feedback_summary(self, channel_id: str, *, limit: int = 100) -> dict[str, int]: ...


@dataclass(frozen=True, slots=True)
class MemoryRecall:
    """Compact prompt context plus privacy-safe counts for tracing."""

    text: str = ""
    fact_count: int = 0
    match_count: int = 0
    feedback_count: int = 0

    @property
    def trace_details(self) -> dict[str, object]:
        return {
            "fact_count": self.fact_count,
            "match_count": self.match_count,
            "feedback_count": self.feedback_count,
        }


class AffinityRetriever:
    """Rank bounded candidates without an external vector service."""

    def __init__(self, source: SocialMemorySource, *, match_limit: int = 4) -> None:
        self._source = source
        self._match_limit = max(0, match_limit)

    async def retrieve(self, envelope: ConversationEnvelope) -> MemoryRecall:
        facts = await self._source.facts(envelope.author_id)
        candidates = await self._source.candidates(envelope.channel_id, envelope.author_id)
        feedback = await self._source.feedback_summary(envelope.channel_id)
        query_terms = _terms(envelope.text)
        scored: list[tuple[int, CandidateMessage]] = []
        for candidate in candidates:
            overlap = len(query_terms & _terms(candidate.content))
            affinity = 3 if candidate.author_id == envelope.author_id else 0
            channel = 1 if candidate.channel_id == envelope.channel_id else 0
            if overlap == 0 and affinity == 0:
                continue
            score = overlap * 2 + affinity + channel
            scored.append((score, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        matches = [candidate for _, candidate in scored[: self._match_limit]]
        sections: list[str] = []
        if facts:
            sections.append(
                "Known explicit user facts:\n"
                + "\n".join(f"- {key.replace('_', ' ')}: {value}" for key, value in facts)
            )
        if matches:
            sections.append(
                "Potentially relevant past messages:\n"
                + "\n".join(f"- {item.author_name}: {item.content[:240]}" for item in matches)
            )
        if feedback:
            summary = ", ".join(f"{signal}={count}" for signal, count in sorted(feedback.items()))
            sections.append(f"Recent reactions to Mika in this channel (aggregate only): {summary}")
        return MemoryRecall(
            "\n\n".join(sections),
            len(facts),
            len(matches),
            sum(feedback.values()),
        )


def _terms(text: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN.finditer(text)}
