"""Prompt retrieval after atomic relationship-profile lifecycle changes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from tests.conversation.relationships.test_service import (
    Classifier,
    Extractor,
    Retriever,
    claim_write,
    evidence_write,
    service_for,
)

from mika.conversation.context.retrieval import AffinityRetriever
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.relationships.activation import ActivationPolicy
from mika.conversation.relationships.consolidation import (
    ConsolidationResult,
    RelationshipConsolidator,
)
from mika.conversation.relationships.contracts import RelationshipClaim
from mika.conversation.relationships.extraction import EvidenceProposal
from mika.conversation.relationships.profile import RelationshipProfile
from mika.conversation.relationships.service import RelationshipMemoryService

NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)


class DisputingConsolidator(RelationshipConsolidator):
    """Produce a disputed durable state for prompt-profile validation."""

    def consolidate(
        self,
        claims: Sequence[RelationshipClaim],
        evidence_by_key: Mapping[str, Sequence[EvidenceProposal]] | None = None,
        *,
        evidence_by_claim_id: Mapping[str, Sequence[EvidenceProposal]] | None = None,
        predecessor: RelationshipProfile | None = None,
        now: datetime,
    ) -> ConsolidationResult:
        disputed = tuple(replace(claim, state="disputed") for claim in claims)
        return super().consolidate(
            disputed,
            evidence_by_key,
            evidence_by_claim_id=evidence_by_claim_id,
            predecessor=predecessor,
            now=now,
        )


class EmptySource:
    """Provide no legacy facts or message candidates during full retrieval."""

    async def facts(self, user_id: str, *, limit: int = 12) -> list[tuple[str, str]]:
        return []

    async def candidates(
        self, channel_id: str, author_id: str, *, limit: int = 80
    ) -> tuple[SimpleNamespace, ...]:
        return ()

    async def feedback_summary(self, channel_id: str, *, limit: int = 100) -> dict[str, int]:
        return {}


async def test_full_retrieval_never_injects_a_profile_entry_demoted_to_disputed(
    tmp_path: Path,
) -> None:
    """The prompt-active profile contains only claims committed as active."""
    service, store, engine = await service_for(tmp_path / "memory.db", Extractor())
    try:
        direct_claim = replace(
            claim_write(
                "drink",
                key="preference:drink",
                value="Tea",
                evidence_class="explicit",
                guild_id="guild-1",
                channel_id="dm-1",
            ),
            visibility_kind="direct_message",
            guild_id=None,
        )
        direct_evidence = replace(
            evidence_write("drink-source", guild_id="guild-1", channel_id="dm-1"),
            visibility_kind="direct_message",
            guild_id=None,
        )
        await store.add_evidence(direct_claim, direct_evidence)
        await store.activate_claim("drink", confirmed_at=NOW)
        await service.consolidate_user(
            "user-1", visibility_kind="direct_message", guild_id=None, channel_id="dm-1"
        )

        disputing_service = RelationshipMemoryService(
            repository=store,
            extractor=Extractor(),
            activation_policy=ActivationPolicy(),
            classifier=Classifier(),
            retriever=Retriever(store),
            consolidator=DisputingConsolidator(),
            clock=lambda: NOW + timedelta(minutes=5),
        )
        await disputing_service.consolidate_user(
            "user-1", visibility_kind="direct_message", guild_id=None, channel_id="dm-1"
        )

        recall = await AffinityRetriever(
            EmptySource(), relationship_source=store, minimum_score=0.0
        ).retrieve(
            ConversationEnvelope(
                "probe",
                "dm-1",
                "",
                "user-1",
                "Ada",
                "Do I like tea?",
                False,
                NOW + timedelta(minutes=6),
            )
        )
        stored = await store.claim("drink")
        assert stored is not None and stored.state == "disputed"
        assert "Tea" not in recall.text
        assert all(not item.startswith("profile:") for item in recall.selected_ids)
    finally:
        await store.close()
        await engine.dispose()
