"""Compatibility coverage for additive relationship-memory schema startup."""

from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from mika.persistence.engine import initialize_schema


async def test_startup_adds_scoped_tables_without_rewriting_existing_profiles(
    tmp_path: Path,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'legacy.db'}")
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "CREATE TABLE relationship_profile_versions ("
                    "profile_version_id VARCHAR(128) PRIMARY KEY, "
                    "subject_user_id VARCHAR(32) NOT NULL, index_text TEXT NOT NULL, "
                    "overview_text TEXT NOT NULL, schema_version VARCHAR(64) NOT NULL, "
                    "generator_version VARCHAR(64) NOT NULL, "
                    "policy_version_id VARCHAR(128) NOT NULL, created_at DATETIME NOT NULL)"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO relationship_profile_versions VALUES "
                    "('legacy-profile', 'user-1', 'index', 'overview', 'v1', 'v1', "
                    "'legacy-policy', '2026-08-17 12:00:00')"
                )
            )
            await initialize_schema(connection)

            tables = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
            legacy_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM relationship_profile_versions "
                    "WHERE profile_version_id = 'legacy-profile'"
                )
            )
        assert {
            "relationship_profile_scopes",
            "relationship_scoped_profile_heads",
            "relationship_consolidation_cadence",
        } <= tables
        assert legacy_count == 1
    finally:
        await engine.dispose()
