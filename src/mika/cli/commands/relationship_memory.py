"""Safe operator workflows for evidence-backed relationship memory."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import typer
from rich.console import Console

from mika.conversation.context.retrieval import MemoryRecall
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.relationships.activation import ActivationPolicy
from mika.conversation.relationships.consolidation import RelationshipConsolidator
from mika.conversation.relationships.contracts import RelationDecision
from mika.conversation.relationships.extraction import (
    EvidenceProposal,
    extract_deterministic_evidence,
)
from mika.conversation.relationships.relation import classify_relation
from mika.conversation.relationships.service import (
    ConsolidationRun,
    ObservationInput,
    ObservationResult,
    RelationshipMemoryService,
)
from mika.core.config import get_settings
from mika.persistence.conversations.archive_reader import ArchiveReader
from mika.persistence.conversations.relationship_memory import RelationshipMemoryRepository
from mika.persistence.conversations.relationship_records import (
    ArchiveCursor,
    ArchiveSourceRecord,
    RelationshipMemoryPolicyVersionRecord,
    RelationshipMemoryStatus,
)
from mika.persistence.engine import init_db, session

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


class BackfillRepository(Protocol):
    """Persistence operations needed for resumable archive ingestion."""

    async def active_policy_version(self) -> RelationshipMemoryPolicyVersionRecord | None: ...

    async def cursor(self, source_name: str) -> ArchiveCursor | None: ...

    async def advance_cursor(self, cursor: ArchiveCursor) -> None: ...


class ArchiveCandidateObserver(Protocol):
    """Candidate-only observation boundary used by historical imports."""

    async def observe_archive_candidate(self, source: ArchiveSourceRecord) -> ObservationResult: ...


@dataclass(frozen=True, slots=True)
class BackfillReport:
    """Content-free result for one bounded archive scan."""

    outcome: str
    processed: int
    discovered: int
    remaining: bool
    invalid_records: int
    policy_version_id: str | None
    cursor: ArchiveCursor | None
    failed_message_id: str | None = None
    failure: str | None = None


class RelationshipMemoryOperator:
    """Run bounded, cursor-safe archive work without changing source retention."""

    def __init__(
        self,
        repository: BackfillRepository,
        archive: ArchiveReader,
        observer: ArchiveCandidateObserver,
        *,
        source_name: str = "shared_archive",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._archive = archive
        self._observer = observer
        self._source_name = source_name
        self._clock = clock or (lambda: datetime.now(UTC))

    async def backfill(self, *, limit: int, dry_run: bool = False) -> BackfillReport:
        """Process one page, checkpointing only successfully committed records."""
        if limit < 1:
            raise ValueError("backfill limit must be positive")
        policy = await self._repository.active_policy_version()
        cursor = await self._repository.cursor(self._source_name)
        if policy is None or not policy.relationship_learning_enabled:
            return BackfillReport(
                "disabled",
                0,
                0,
                False,
                0,
                None if policy is None else policy.policy_version_id,
                cursor,
            )
        page = self._archive.scan_after(cursor, limit + 1)
        selected = page.records[:limit]
        if dry_run:
            return BackfillReport(
                "dry_run",
                0,
                len(selected),
                len(page.records) > limit,
                page.invalid_records,
                policy.policy_version_id,
                cursor,
            )
        processed = 0
        for source in selected:
            try:
                result = await self._observer.observe_archive_candidate(source)
            except Exception as error:
                return BackfillReport(
                    "degraded",
                    processed,
                    len(selected),
                    True,
                    page.invalid_records,
                    policy.policy_version_id,
                    cursor,
                    source.discord_message_id,
                    type(error).__name__,
                )
            if result.outcome != "observed" or result.policy_version_id != policy.policy_version_id:
                reason = (
                    "policy_changed"
                    if result.policy_version_id != policy.policy_version_id
                    else f"observation_{result.outcome}"
                )
                return BackfillReport(
                    "degraded",
                    processed,
                    len(selected),
                    True,
                    page.invalid_records,
                    result.policy_version_id,
                    cursor,
                    source.discord_message_id,
                    reason,
                )
            cursor = ArchiveCursor(
                self._source_name,
                source.archive_created_at,
                source.discord_message_id,
                result.policy_version_id,
                self._clock(),
            )
            await self._repository.advance_cursor(cursor)
            processed += 1
        outcome = "degraded" if page.invalid_records else "ok"
        return BackfillReport(
            outcome,
            processed,
            len(selected),
            len(page.records) > limit,
            page.invalid_records,
            policy.policy_version_id,
            cursor,
        )


def deletion_confirmation(subject_user_id: str) -> str:
    """Return the exact acknowledgement required for derived-memory deletion."""
    return f"delete-derived-memory:{subject_user_id}"


def render_status(status: RelationshipMemoryStatus) -> dict[str, object]:
    """Render only aggregate and checkpoint metadata for operator output."""
    return {
        "claims": status.claim_count,
        "candidates": status.candidate_count,
        "active_profiles": status.active_profile_count,
        "recalls": status.recall_count,
        "active_policy_version": status.active_policy_version_id,
        "learning_enabled": status.learning_enabled,
        "last_consolidation_at": _iso(status.last_consolidation_at),
        "archive": {
            "source": status.archive_source_name,
            "message_id": status.archive_message_id,
            "updated_at": _iso(status.archive_updated_at),
        },
        "operation_health": status.operation_health,
    }


def archive_source_health(path: Path | None) -> dict[str, bool]:
    """Report archive availability without opening or exposing its path."""
    return {"configured": path is not None, "available": bool(path and path.is_file())}


class _DeterministicExtractor:
    async def extract(
        self, observation: ObservationInput, relation: RelationDecision
    ) -> tuple[EvidenceProposal, ...]:
        return extract_deterministic_evidence(
            observation.text,
            source_message_id=observation.message_id,
            source_timestamp=observation.created_at,
            relation=relation,
        )


class _DeterministicClassifier:
    def classify(self, observation: ObservationInput) -> RelationDecision:
        return classify_relation(observation.text)


class _EmptyRetriever:
    async def retrieve(self, envelope: ConversationEnvelope) -> MemoryRecall:
        return MemoryRecall(relationship_retrieval=True)


def _service(
    repository: RelationshipMemoryRepository, archive: ArchiveReader
) -> RelationshipMemoryService:
    return RelationshipMemoryService(
        repository=repository,
        extractor=_DeterministicExtractor(),
        activation_policy=ActivationPolicy(),
        classifier=_DeterministicClassifier(),
        retriever=_EmptyRetriever(),
        consolidator=RelationshipConsolidator(),
        pending_source=archive,
    )


async def _status_command() -> dict[str, object]:
    await init_db()
    async with session() as active:
        result = render_status(await RelationshipMemoryRepository(active).status())
        source = archive_source_health(get_settings().shared_archive_path)
        result["archive_source"] = source
        result["degraded"] = not source["available"]
        return result


async def _backfill_command(limit: int, dry_run: bool) -> BackfillReport:
    archive_path = get_settings().shared_archive_path
    if archive_path is None:
        raise FileNotFoundError("MIKA_SHARED_ARCHIVE_PATH is not configured")
    await init_db()
    async with session() as active:
        repository = RelationshipMemoryRepository(active)
        archive = ArchiveReader(archive_path)
        operator = RelationshipMemoryOperator(repository, archive, _service(repository, archive))
        return await operator.backfill(limit=limit, dry_run=dry_run)


@app.command()
def status() -> None:
    """Show content-free relationship-memory counts and checkpoint health."""
    try:
        console.print_json(json.dumps(asyncio.run(_status_command())))
    except Exception as error:
        console.print_json(json.dumps({"degraded": True, "failure": type(error).__name__}))
        raise typer.Exit(1) from error


@app.command()
def backfill(limit: int = 100, dry_run: bool = False) -> None:
    """Process one bounded archive page after the durable checkpoint."""
    try:
        report = asyncio.run(_backfill_command(limit, dry_run))
    except Exception as error:
        console.print_json(json.dumps({"degraded": True, "failure": type(error).__name__}))
        raise typer.Exit(1) from error
    console.print_json(json.dumps(asdict(report), default=str))


async def _inspect_command(subject_user_id: str) -> dict[str, object]:
    await init_db()
    async with session() as active:
        repository = RelationshipMemoryRepository(active)
        claims = await repository.claims_for_subject(subject_user_id)
        evidence = await repository.evidence_for_claims([claim.claim_id for claim in claims])
        profiles = await repository.active_profiles_for_subject(subject_user_id)
        sources: dict[str, list[str]] = {}
        for item in evidence:
            sources.setdefault(item.claim_id, []).append(item.source_message_id)
        return {
            "subject_user_id": subject_user_id,
            "claims": [
                {
                    "claim_id": claim.claim_id,
                    "state": claim.state,
                    "evidence_class": claim.evidence_class,
                    "observation_count": claim.observation_count,
                    "source_message_ids": sorted(sources.get(claim.claim_id, []), key=int),
                }
                for claim in claims
            ],
            "active_profiles": [
                {
                    "visibility_kind": profile.visibility_kind,
                    "guild_id": profile.guild_id,
                    "channel_id": profile.channel_id,
                    "profile_version_id": profile.profile_version_id,
                }
                for profile in profiles
            ],
        }


@app.command()
def inspect(subject_user_id: str) -> None:
    """Show source IDs and lifecycle metadata without claim or message text."""
    console.print_json(json.dumps(asyncio.run(_inspect_command(subject_user_id))))


@app.command("delete-user")
def delete_user(subject_user_id: str, confirm: str = "") -> None:
    """Delete one user's derived relationship state, preserving the archive."""
    if confirm != deletion_confirmation(subject_user_id):
        console.print(f"Confirmation required: {deletion_confirmation(subject_user_id)}")
        raise typer.Exit(2)

    async def execute() -> None:
        await init_db()
        async with session() as active:
            await RelationshipMemoryRepository(active).delete_user_memory(subject_user_id)

    asyncio.run(execute())
    console.print_json(json.dumps({"deleted_subject_user_id": subject_user_id}))


@app.command()
def consolidate(
    subject_user_id: str,
    visibility_kind: str = "guild",
    guild_id: str | None = None,
    channel_id: str | None = None,
) -> None:
    """Consolidate candidates for one person into an immutable profile version."""

    async def execute() -> ConsolidationRun:
        await init_db()
        async with session() as active:
            repository = RelationshipMemoryRepository(active)
            archive = ArchiveReader(
                get_settings().shared_archive_path or get_settings().data_dir / "missing"
            )
            return await _service(repository, archive).consolidate_user(
                subject_user_id,
                visibility_kind=visibility_kind,
                guild_id=guild_id,
                channel_id=channel_id,
            )

    console.print_json(json.dumps(asdict(asyncio.run(execute())), default=str))


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()
