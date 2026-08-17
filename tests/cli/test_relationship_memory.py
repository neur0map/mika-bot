"""Operator workflows for safe relationship-memory archive backfill."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.conversation.relationships.test_service import (
    Extractor,
    claim_write,
    evidence_write,
    service_for,
)
from typer.testing import CliRunner

from mika.cli.app import app as cli_app
from mika.cli.commands.relationship_memory import (
    RelationshipMemoryOperator,
    archive_source_health,
    deletion_confirmation,
    render_status,
)
from mika.conversation.relationships.service import ObservationResult
from mika.persistence.conversations.archive_reader import ArchiveReader
from mika.persistence.conversations.relationship_records import (
    ArchiveCursor,
    ArchiveSourceRecord,
    RelationshipMemoryPolicyVersionRecord,
    RelationshipMemoryStatus,
)

NOW = datetime(2026, 8, 18, 12, tzinfo=UTC)


class Repository:
    """In-memory cursor and policy boundary for operator behavior tests."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.saved_cursor: ArchiveCursor | None = None
        self.policy = RelationshipMemoryPolicyVersionRecord(
            "policy-1", enabled, False, False, False, {"dm_to_public": False}, "test", NOW
        )

    async def active_policy_version(self) -> RelationshipMemoryPolicyVersionRecord:
        return self.policy

    async def cursor(self, source_name: str) -> ArchiveCursor | None:
        return self.saved_cursor

    async def advance_cursor(self, cursor: ArchiveCursor) -> None:
        self.saved_cursor = cursor


class CandidateObserver:
    """Records candidate-only archive observations and can reproduce a crash."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.seen: list[str] = []

    async def observe_archive_candidate(self, source: ArchiveSourceRecord) -> ObservationResult:
        if source.discord_message_id == self.fail_on:
            raise RuntimeError("extractor failed")
        self.seen.append(source.discord_message_id)
        return ObservationResult("observed", "policy-1")


class PolicySwitchObserver:
    """Changes the effective policy after one committed source."""

    def __init__(self, repository: Repository) -> None:
        self.repository = repository
        self.calls = 0

    async def observe_archive_candidate(self, source: ArchiveSourceRecord) -> ObservationResult:
        self.calls += 1
        if self.calls == 1:
            return ObservationResult("observed", "policy-1")
        self.repository.policy = RelationshipMemoryPolicyVersionRecord(
            "policy-2", True, False, False, False, {"dm_to_public": False}, "changed", NOW
        )
        return ObservationResult("observed", "policy-2")


class DisabledObserver:
    async def observe_archive_candidate(self, source: ArchiveSourceRecord) -> ObservationResult:
        return ObservationResult("disabled", "policy-1")


def _archive(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE messages (
                id TEXT PRIMARY KEY, author TEXT, author_id TEXT, content TEXT,
                created_at TEXT, guild_id TEXT, channel_id TEXT,
                discord_message_id TEXT, metadata_json TEXT
            )"""
        )
        connection.executemany(
            "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?)",
            [
                ("row-1", "A", "user-a", "first", NOW.isoformat(), "g", "c", "100", "{}"),
                ("row-2", "B", "user-b", "second", NOW.isoformat(), "g", "c", "101", "{}"),
                ("row-3", "A", "user-a", "third", NOW.isoformat(), "g", "c", "102", "{}"),
                ("bad-id", "A", "user-a", "private", NOW.isoformat(), "g", "c", "x", "{}"),
                ("bad-time", "A", "user-a", "private", "not-a-time", "g", "c", "103", "{}"),
            ],
        )


@pytest.mark.asyncio
async def test_backfill_resumes_strictly_after_compound_cursor(tmp_path: Path) -> None:
    path = tmp_path / "archive.sqlite3"
    _archive(path)
    before = hashlib.sha256(path.read_bytes()).digest()
    repository = Repository()
    observer = CandidateObserver()
    operator = RelationshipMemoryOperator(
        repository, ArchiveReader(path), observer, clock=lambda: NOW
    )

    first = await operator.backfill(limit=2)
    second = await operator.backfill(limit=2)

    assert (first.processed, first.remaining, first.invalid_records) == (2, True, 2)
    assert (second.processed, second.remaining) == (1, False)
    assert observer.seen == ["100", "101", "102"]
    assert repository.saved_cursor is not None
    assert repository.saved_cursor.discord_message_id == "102"
    assert hashlib.sha256(path.read_bytes()).digest() == before


@pytest.mark.asyncio
async def test_backfill_stops_at_failure_and_retries_failed_record(tmp_path: Path) -> None:
    path = tmp_path / "archive.sqlite3"
    _archive(path)
    repository = Repository()
    failing = CandidateObserver(fail_on="101")
    operator = RelationshipMemoryOperator(
        repository, ArchiveReader(path), failing, clock=lambda: NOW
    )

    report = await operator.backfill(limit=3)

    assert (report.processed, report.failed_message_id, report.failure) == (
        1,
        "101",
        "RuntimeError",
    )
    assert repository.saved_cursor is not None
    assert repository.saved_cursor.discord_message_id == "100"

    recovered = CandidateObserver()
    retry = RelationshipMemoryOperator(
        repository, ArchiveReader(path), recovered, clock=lambda: NOW
    )
    report = await retry.backfill(limit=3)

    assert report.processed == 2
    assert recovered.seen == ["101", "102"]


@pytest.mark.asyncio
async def test_disabled_learning_and_dry_run_never_advance_cursor(tmp_path: Path) -> None:
    path = tmp_path / "archive.sqlite3"
    _archive(path)
    observer = CandidateObserver()
    disabled = Repository(enabled=False)
    operator = RelationshipMemoryOperator(
        disabled, ArchiveReader(path), observer, clock=lambda: NOW
    )

    disabled_report = await operator.backfill(limit=10)
    dry_report = await RelationshipMemoryOperator(
        Repository(), ArchiveReader(path), observer, clock=lambda: NOW
    ).backfill(limit=10, dry_run=True)

    assert disabled_report.outcome == "disabled"
    assert dry_report.outcome == "dry_run"
    assert dry_report.processed == 0
    assert dry_report.discovered == 3
    assert observer.seen == []
    assert disabled.saved_cursor is None


@pytest.mark.asyncio
async def test_backfill_stops_before_checkpointing_a_mid_page_policy_change(tmp_path: Path) -> None:
    path = tmp_path / "archive.sqlite3"
    _archive(path)
    repository = Repository()
    operator = RelationshipMemoryOperator(
        repository, ArchiveReader(path), PolicySwitchObserver(repository), clock=lambda: NOW
    )

    report = await operator.backfill(limit=3)

    assert report.processed == 1
    assert report.failure == "policy_changed"
    assert report.failed_message_id == "101"
    assert repository.saved_cursor is not None
    assert repository.saved_cursor.discord_message_id == "100"
    assert repository.saved_cursor.policy_version_id == "policy-1"


@pytest.mark.asyncio
async def test_backfill_never_checkpoints_a_disabled_observation(tmp_path: Path) -> None:
    path = tmp_path / "archive.sqlite3"
    _archive(path)
    repository = Repository()

    report = await RelationshipMemoryOperator(
        repository, ArchiveReader(path), DisabledObserver(), clock=lambda: NOW
    ).backfill(limit=1)

    assert report.processed == 0
    assert report.failure == "observation_disabled"
    assert repository.saved_cursor is None


def test_archive_reader_accepts_training_archive_schema_without_copying_resources(
    tmp_path: Path,
) -> None:
    path = tmp_path / "training.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE messages (
                id TEXT PRIMARY KEY, author_id TEXT, author_name TEXT, content TEXT,
                created_at TEXT, guild_id TEXT, channel_id TEXT
            )"""
        )
        connection.execute(
            "INSERT INTO messages VALUES (?,?,?,?,?,?,?)",
            ("900", "user-a", "A", "https://example.test/a.gif", NOW.isoformat(), "g", "c"),
        )
        connection.execute(
            "CREATE TABLE resources (id INTEGER PRIMARY KEY, canonical_url TEXT, storage_path TEXT)"
        )
        connection.execute(
            "INSERT INTO resources VALUES (1, 'https://example.test/a.gif', 'objects/a')"
        )

    page = ArchiveReader(path).scan_after(None, 10)

    assert [item.discord_message_id for item in page.records] == ["900"]
    assert page.records[0].source_id == "900"
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM resources").fetchone() == (1,)


@pytest.mark.asyncio
async def test_archive_observation_stays_candidate_until_consolidation(tmp_path: Path) -> None:
    service, repository, engine = await service_for(tmp_path / "memory.sqlite3", Extractor())
    source = ArchiveSourceRecord(
        "shared_archive", "row-1", "100", "user-1", "A", "I like Hades", NOW, "channel", "g", "c"
    )
    try:
        await service.observe_archive_candidate(source)
        await service.observe_archive_candidate(source)

        claims = await repository.claims_for_subject("user-1")
        assert len(claims) == 1
        assert claims[0].state == "candidate"
        assert claims[0].observation_count == 1
    finally:
        await repository.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_archive_candidates_keep_person_and_channel_scope_isolated(tmp_path: Path) -> None:
    service, repository, engine = await service_for(tmp_path / "memory.sqlite3", Extractor())
    first = ArchiveSourceRecord(
        "shared_archive",
        "row-1",
        "100",
        "user-1",
        "A",
        "I like Hades",
        NOW,
        "channel",
        "g-1",
        "c-1",
    )
    second = ArchiveSourceRecord(
        "shared_archive",
        "row-2",
        "101",
        "user-2",
        "B",
        "I like Hades",
        NOW,
        "channel",
        "g-2",
        "c-2",
    )
    try:
        await service.observe_archive_candidate(first)
        await service.observe_archive_candidate(second)

        user_one = await repository.claims_for_subject("user-1")
        user_two = await repository.claims_for_subject("user-2")
        assert {(item.subject_user_id, item.guild_id, item.channel_id) for item in user_one} == {
            ("user-1", "g-1", "c-1")
        }
        assert {(item.subject_user_id, item.guild_id, item.channel_id) for item in user_two} == {
            ("user-2", "g-2", "c-2")
        }
    finally:
        await repository.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_consolidation_only_uses_the_requested_exact_scope(tmp_path: Path) -> None:
    service, repository, engine = await service_for(tmp_path / "memory.sqlite3", Extractor())
    try:
        await repository.add_evidence(
            claim_write(
                "guild-one",
                key="project",
                value="private-alpha",
                evidence_class="explicit",
                guild_id="g-1",
                channel_id="c-1",
            ),
            evidence_write("100", guild_id="g-1", channel_id="c-1"),
        )
        await repository.activate_claim("guild-one", confirmed_at=NOW)
        await repository.add_evidence(
            claim_write(
                "guild-two",
                key="project",
                value="private-beta",
                evidence_class="explicit",
                guild_id="g-2",
                channel_id="c-2",
            ),
            evidence_write("101", guild_id="g-2", channel_id="c-2"),
        )
        await repository.activate_claim("guild-two", confirmed_at=NOW)

        await service.consolidate_user(
            "user-1", visibility_kind="guild", guild_id="g-1", channel_id="c-1"
        )
        profile = await repository.active_profile("user-1")

        assert profile is not None
        assert "private-alpha" in profile.overview_text
        assert "private-beta" not in profile.overview_text
        assert {link.claim_id for link in profile.claim_links} == {"guild-one"}
    finally:
        await repository.close()
        await engine.dispose()


def test_status_rendering_is_content_free_and_deletion_requires_exact_user() -> None:
    snapshot = RelationshipMemoryStatus(
        2, 1, 1, 4, "policy-1", True, NOW, "weekly", "100", NOW, {"recall": {"ok": 4}}
    )

    rendered = render_status(snapshot)

    assert rendered["active_policy_version"] == "policy-1"
    assert rendered["claims"] == 2
    assert rendered["operation_health"] == {"recall": {"ok": 4}}
    assert "query" not in repr(rendered).casefold()
    assert "content" not in repr(rendered).casefold()
    assert deletion_confirmation("42") == "delete-derived-memory:42"
    assert archive_source_health(None) == {"configured": False, "available": False}


def test_relationship_memory_commands_are_operator_visible() -> None:
    result = CliRunner().invoke(cli_app, ["relationship-memory", "--help"])

    assert result.exit_code == 0
    assert all(
        command in result.stdout
        for command in ("backfill", "consolidate", "delete-user", "inspect", "status")
    )
