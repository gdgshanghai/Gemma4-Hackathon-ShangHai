from __future__ import annotations

import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from backend.storage.database import (
    MigrationChecksumError,
    connect_database,
    run_migrations,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = PROJECT_ROOT / "backend" / "storage" / "migrations"
REQUIRED_TABLES = {
    "schema_migrations",
    "school_briefs",
    "evening_sessions",
    "task_items",
    "coverage_diffs",
    "plans",
    "plan_blocks",
    "task_outcomes",
    "calibration_events",
    "observation_events",
    "llm_runs",
    "tool_runs",
    "harness_traces",
    "harness_trace_events",
    "audit_events",
    "idempotency_records",
    "profile_state",
    "profile_versions",
    "profile_observation_events",
    "calibration_sessions",
    "calibration_turn_receipts",
    "calibration_drafts",
    "calibration_commits",
    "calibration_checkpoints",
    "calibration_audit_events",
    "school_brief_revisions",
    "daily_evening_sessions",
}


def _schema_snapshot(connection: sqlite3.Connection) -> list[tuple[object, ...]]:
    return [
        tuple(row)
        for row in connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_schema
            WHERE name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        ).fetchall()
    ]


def test_all_migrations_create_every_required_table(tmp_path: Path) -> None:
    database_path = tmp_path / "studypilot.db"

    applied = run_migrations(database_path)

    assert applied == [1, 2, 3, 4, 5, 6, 7, 8]
    with connect_database(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
        migrations = connection.execute(
            """
            SELECT version, name, length(checksum)
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()
    assert REQUIRED_TABLES <= tables
    assert [tuple(row) for row in migrations] == [
        (1, "initial", 64),
        (2, "task_planning_fields", 64),
        (3, "harness_traces", 64),
        (4, "family_context", 64),
        (5, "daily_evening_registry", 64),
        (6, "evening_continuity", 64),
        (7, "task_schedule_snapshot", 64),
        (8, "estimate_breakdown", 64),
    ]


def test_evening_continuity_migration_adds_assignment_storage(tmp_path: Path) -> None:
    database_path = tmp_path / "studypilot.db"

    applied = run_migrations(database_path)

    assert 6 in applied
    with connect_database(database_path) as connection:
        session_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(evening_sessions)")
        }
        task_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(task_items)")
        }
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }

    assert "planning_date" in session_columns
    assert {"assignment_id", "deadline_text", "remaining_percent"} <= task_columns
    assert {"assignment_obligations", "assignment_schedule_events"} <= tables


def test_estimate_breakdown_migration_adds_empty_component_snapshots(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "studypilot.db"

    applied = run_migrations(database_path)

    assert 8 in applied
    with connect_database(database_path) as connection:
        task_columns = {
            str(row["name"]): str(row["dflt_value"])
            for row in connection.execute("PRAGMA table_info(task_items)")
        }
        assignment_columns = {
            str(row["name"]): str(row["dflt_value"])
            for row in connection.execute("PRAGMA table_info(assignment_obligations)")
        }

    assert task_columns["estimate_breakdown_json"] == "'[]'"
    assert task_columns["estimate_signature"] == "None"
    assert assignment_columns["estimate_breakdown_json"] == "'[]'"
    assert assignment_columns["estimate_signature"] == "None"


def test_second_migration_run_makes_no_schema_or_history_changes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "studypilot.db"
    run_migrations(database_path)
    with connect_database(database_path) as connection:
        schema_before = _schema_snapshot(connection)
        history_before = [
            tuple(row)
            for row in connection.execute(
                "SELECT version, name, checksum, applied_at FROM schema_migrations"
            )
        ]

    applied = run_migrations(database_path)

    with connect_database(database_path) as connection:
        assert _schema_snapshot(connection) == schema_before
        history_after = [
            tuple(row)
            for row in connection.execute(
                "SELECT version, name, checksum, applied_at FROM schema_migrations"
            )
        ]
    assert applied == []
    assert history_after == history_before


def test_connection_enables_foreign_keys_wal_and_busy_timeout(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "studypilot.db"

    with connect_database(database_path) as connection:
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

    assert foreign_keys == 1
    assert journal_mode.lower() == "wal"
    assert busy_timeout == 5_000


def test_migration_checksum_mismatch_raises(tmp_path: Path) -> None:
    database_path = tmp_path / "studypilot.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    migration_path = migrations_dir / "0001_initial.sql"
    shutil.copy2(MIGRATIONS_DIR / migration_path.name, migration_path)
    run_migrations(database_path, migrations_dir=migrations_dir)
    migration_path.write_text(
        migration_path.read_text(encoding="utf-8") + "\n-- tampered\n",
        encoding="utf-8",
    )

    with pytest.raises(MigrationChecksumError, match="version 1"):
        run_migrations(database_path, migrations_dir=migrations_dir)


def test_later_migration_backs_up_non_empty_database(tmp_path: Path) -> None:
    database_path = tmp_path / "studypilot.db"
    migrations_dir = tmp_path / "migrations"
    backups_dir = tmp_path / "backups"
    migrations_dir.mkdir()
    shutil.copy2(
        MIGRATIONS_DIR / "0001_initial.sql",
        migrations_dir / "0001_initial.sql",
    )
    run_migrations(
        database_path,
        migrations_dir=migrations_dir,
        backup_dir=backups_dir,
    )
    with connect_database(database_path) as connection:
        connection.execute(
            """
            INSERT INTO school_briefs (
                id, brief_date, source_path, content_sha256, raw_text
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "brief-1",
                "2026-07-11",
                "data/school/2026-07-11.md",
                "a" * 64,
                "Math exercises 1-4",
            ),
        )
        connection.commit()
    (migrations_dir / "0002_marker.sql").write_text(
        "CREATE TABLE migration_marker (id INTEGER PRIMARY KEY);\n",
        encoding="utf-8",
    )

    applied = run_migrations(
        database_path,
        migrations_dir=migrations_dir,
        backup_dir=backups_dir,
    )

    backups = list(backups_dir.glob("studypilot-*.db"))
    assert applied == [2]
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        stored = backup.execute(
            "SELECT raw_text FROM school_briefs WHERE id = 'brief-1'"
        ).fetchone()
        marker = backup.execute(
            "SELECT name FROM sqlite_schema WHERE name = 'migration_marker'"
        ).fetchone()
    assert stored == ("Math exercises 1-4",)
    assert marker is None


def test_task_planning_migration_preserves_seeded_task_and_records_history(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "studypilot.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    shutil.copy2(
        MIGRATIONS_DIR / "0001_initial.sql",
        migrations_dir / "0001_initial.sql",
    )
    assert run_migrations(database_path, migrations_dir=migrations_dir) == [1]
    with connect_database(database_path) as connection:
        connection.execute(
            """
            INSERT INTO evening_sessions (
                id, session_date, timezone, sleep_time, stage,
                available_minutes
            ) VALUES ('session-1', '2026-07-11', 'Asia/Shanghai', '22:00',
                      'inventory_confirmed', 120)
            """
        )
        connection.execute(
            """
            INSERT INTO task_items (
                id, session_id, title, subject, source, completion_state,
                estimated_minutes, conservative_minutes, priority
            ) VALUES ('task-1', 'session-1', 'Existing task', 'math', 'school',
                      'pending', 20, 25, 1)
            """
        )
        connection.commit()
    shutil.copy2(
        MIGRATIONS_DIR / "0002_task_planning_fields.sql",
        migrations_dir / "0002_task_planning_fields.sql",
    )

    applied = run_migrations(
        database_path,
        migrations_dir=migrations_dir,
        backup_dir=tmp_path / "backups",
    )

    with connect_database(database_path) as connection:
        row = connection.execute(
            """
            SELECT title, task_type, must_do_tonight, child_estimate_minutes,
                   estimate_source, estimate_confidence, avoidance_score,
                   preference_score
            FROM task_items
            WHERE id = 'task-1'
            """
        ).fetchone()
        history = connection.execute(
            """
            SELECT version, name, checksum
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()

    assert applied == [2]
    assert tuple(row) == (
        "Existing task",
        None,
        0,
        None,
        "domain_default",
        "low",
        0,
        0,
    )
    assert [(item[0], item[1]) for item in history] == [
        (1, "initial"),
        (2, "task_planning_fields"),
    ]
    assert history[0][2] != history[1][2]


def test_concurrent_migration_runners_apply_each_version_once(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "concurrent.db"
    runner_count = 8
    barrier = Barrier(runner_count)

    def migrate(_: int) -> list[int]:
        barrier.wait()
        return run_migrations(database_path)

    with ThreadPoolExecutor(max_workers=runner_count) as executor:
        results = list(executor.map(migrate, range(runner_count)))

    assert results.count([1, 2, 3, 4, 5, 6, 7, 8]) == 1
    assert results.count([]) == runner_count - 1
    with connect_database(database_path) as connection:
        history_count = connection.execute(
            "SELECT count(*) FROM schema_migrations "
            "WHERE version IN (1, 2, 3, 4, 5, 6, 7, 8)"
        ).fetchone()[0]
    assert history_count == 8


def test_family_context_migration_upgrades_seeded_0003_without_loss(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "upgrade.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    for name in (
        "0001_initial.sql",
        "0002_task_planning_fields.sql",
        "0003_harness_traces.sql",
    ):
        shutil.copy2(MIGRATIONS_DIR / name, migrations_dir / name)
    assert run_migrations(database_path, migrations_dir=migrations_dir) == [1, 2, 3]
    with connect_database(database_path) as connection:
        connection.execute(
            """
            INSERT INTO school_briefs (
                id, brief_date, source_path, content_sha256, raw_text, created_at
            ) VALUES ('legacy-brief', '2026-07-11', 'legacy/manual.txt', ?,
                      'legacy-seed', '2026-07-11T12:00:00+00:00')
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO harness_traces (
                id, trace_id, workflow_phase, actor, role, expected_version,
                harness_version, status, started_at
            ) VALUES ('legacy-trace-row', 'legacy-trace', 'profile_propose',
                      'legacy-actor', 'parent', 0, 'v13-test', 'completed',
                      '2026-07-11T12:00:00+00:00')
            """
        )
        connection.commit()
    shutil.copy2(
        MIGRATIONS_DIR / "0004_family_context.sql",
        migrations_dir / "0004_family_context.sql",
    )

    applied = run_migrations(
        database_path,
        migrations_dir=migrations_dir,
        backup_dir=tmp_path / "backups",
    )

    with connect_database(database_path) as connection:
        legacy_brief = connection.execute(
            "SELECT source_path, raw_text FROM school_briefs WHERE id = 'legacy-brief'"
        ).fetchone()
        legacy_trace = connection.execute(
            "SELECT actor, role FROM harness_traces WHERE trace_id = 'legacy-trace'"
        ).fetchone()
        profile_state = connection.execute(
            "SELECT singleton, profile_version FROM profile_state"
        ).fetchone()
        history = connection.execute(
            "SELECT version, name, length(checksum) FROM schema_migrations ORDER BY version"
        ).fetchall()
        foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    assert applied == [4]
    assert tuple(legacy_brief) == ("legacy/manual.txt", "legacy-seed")
    assert tuple(legacy_trace) == ("legacy-actor", "parent")
    assert tuple(profile_state) == (1, 0)
    assert [tuple(row) for row in history] == [
        (1, "initial", 64),
        (2, "task_planning_fields", 64),
        (3, "harness_traces", 64),
        (4, "family_context", 64),
    ]
    assert foreign_key_violations == []


def test_daily_evening_registry_preserves_duplicates_and_selects_latest(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "daily-registry.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    for name in (
        "0001_initial.sql",
        "0002_task_planning_fields.sql",
        "0003_harness_traces.sql",
        "0004_family_context.sql",
    ):
        shutil.copy2(MIGRATIONS_DIR / name, migrations_dir / name)
    assert run_migrations(database_path, migrations_dir=migrations_dir) == [1, 2, 3, 4]
    with connect_database(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO evening_sessions (
                id, session_date, timezone, sleep_time, stage, version,
                available_minutes, created_at, updated_at
            ) VALUES (?, '2026-07-12', 'Asia/Shanghai', '22:00', ?, 1, 120, ?, ?)
            """,
            [
                (
                    "legacy-first",
                    "closed",
                    "2026-07-12T10:00:00+00:00",
                    "2026-07-12T10:00:00+00:00",
                ),
                (
                    "real-latest",
                    "capacity_conflict",
                    "2026-07-12T11:00:00+00:00",
                    "2026-07-12T11:00:00+00:00",
                ),
            ],
        )
        connection.commit()
    shutil.copy2(
        MIGRATIONS_DIR / "0005_daily_evening_registry.sql",
        migrations_dir / "0005_daily_evening_registry.sql",
    )

    assert run_migrations(
        database_path,
        migrations_dir=migrations_dir,
        backup_dir=tmp_path / "backups",
    ) == [5]

    with connect_database(database_path) as connection:
        session_ids = [
            row[0]
            for row in connection.execute(
                "SELECT id FROM evening_sessions ORDER BY created_at"
            )
        ]
        registry = connection.execute(
            "SELECT session_date, session_id FROM daily_evening_sessions"
        ).fetchall()
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            connection.execute(
                """
                INSERT INTO daily_evening_sessions (
                    session_date, session_id, registered_at
                ) VALUES ('2026-07-12', 'legacy-first', '2026-07-12T12:00:00+00:00')
                """
            )

    assert session_ids == ["legacy-first", "real-latest"]
    assert [tuple(row) for row in registry] == [("2026-07-12", "real-latest")]


def _seed_family_immutable_rows(connection: sqlite3.Connection) -> None:
    now = "2026-07-11T12:00:00+00:00"
    connection.execute(
        """
        INSERT INTO calibration_sessions (
            id, calibration_version, state, base_profile_version, profile_version,
            input_receipt_id, pending_kind, pending_entity_id, created_at, updated_at
        ) VALUES ('calibration-1', 1, 'input_saved', 0, 0, 'receipt-1',
                  NULL, NULL, ?, ?)
        """,
        (now, now),
    )
    connection.execute(
        """
        INSERT INTO calibration_turn_receipts (
            id, calibration_id, operation, key_hash, request_hash, actor, role,
            content_sha256, raw_text, base_profile_version, created_at
        ) VALUES ('receipt-1', 'calibration-1', 'save_calibration_input', ?, ?,
                  'parent-1', 'parent', ?, 'local evidence', 0, ?)
        """,
        ("1" * 64, "2" * 64, "3" * 64, now),
    )
    connection.execute(
        """
        INSERT INTO calibration_drafts (
            id, calibration_id, receipt_id, base_profile_version, proposal_digest,
            draft_digest, operations_json, result_json, revises_draft_id, created_at
        ) VALUES ('draft-1', 'calibration-1', 'receipt-1', 0, ?, ?, '[]', '{}', NULL, ?)
        """,
        ("4" * 64, "5" * 64, now),
    )
    connection.execute(
        """
        INSERT INTO calibration_commits (
            id, calibration_id, draft_id, resulting_profile_version,
            accepted_operation_ids_json, confirmed_by, committed_at
        ) VALUES ('commit-1', 'calibration-1', 'draft-1', 1, '["operation-1"]',
                  'parent-1', ?)
        """,
        (now,),
    )
    connection.execute(
        """
        INSERT INTO profile_versions (
            profile_version, commit_id, reason, committed_at
        ) VALUES (1, 'commit-1', 'parent_confirmed_patch', ?)
        """,
        (now,),
    )
    connection.execute(
        """
        INSERT INTO profile_observation_events (
            id, operation_id, profile_version, canonical_order, action, category,
            subject, task_type, metric, value_text, value_number, unit, confidence,
            sample_count, observed_at, target_event_id, source, evidence_level,
            confirmed_by, committed_at
        ) VALUES ('event-1', 'operation-1', 1, 0, 'assert', 'subject_performance',
                  'General subject', 'written', 'assessment_level', 'developing',
                  NULL, NULL, 0.8, NULL, ?, NULL, 'parent', 'parent_confirmed',
                  'parent-1', ?)
        """,
        (now, now),
    )
    connection.execute(
        """
        INSERT INTO calibration_checkpoints (
            id, calibration_id, calibration_version, profile_version, state,
            resume_stage, pending_kind, pending_entity_id,
            last_stable_calibration_version, last_stable_profile_version,
            input_receipt_id, trace_id, outcome_json, occurred_at
        ) VALUES ('checkpoint-1', 'calibration-1', 1, 0, 'input_saved',
                  'profile_propose', NULL, NULL, 1, 0, 'receipt-1', 'trace-1',
                  NULL, ?)
        """,
        (now,),
    )
    connection.execute(
        """
        INSERT INTO calibration_audit_events (
            id, calibration_id, event_type, actor, role, profile_version,
            payload_json, trace_id, occurred_at, created_at
        ) VALUES ('audit-1', 'calibration-1', 'profile_committed', 'parent-1',
                  'parent', 1, '{}', 'trace-1', ?, ?)
        """,
        (now, now),
    )
    connection.execute(
        """
        INSERT INTO school_brief_revisions (
            id, brief_date, revision, content_sha256, raw_text, source, created_at
        ) VALUES ('school-1-r1', '2026-07-11', 1, ?, '', 'manual-paste', ?)
        """,
        ("6" * 64, now),
    )


def test_family_context_foreign_keys_are_one_way_and_enforced(tmp_path: Path) -> None:
    database_path = tmp_path / "foreign-keys.db"
    run_migrations(database_path)
    with connect_database(database_path) as connection:
        _seed_family_immutable_rows(connection)
        connection.commit()
        profile_version_fks = {
            (str(row[2]), str(row[3]), str(row[4]))
            for row in connection.execute("PRAGMA foreign_key_list(profile_versions)")
        }
        commit_fks = {
            (str(row[2]), str(row[3]), str(row[4]))
            for row in connection.execute("PRAGMA foreign_key_list(calibration_commits)")
        }
        observation_fks = {
            (str(row[2]), str(row[3]), str(row[4]))
            for row in connection.execute("PRAGMA foreign_key_list(profile_observation_events)")
        }
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute(
                """
                INSERT INTO profile_versions (
                    profile_version, commit_id, reason, committed_at
                ) VALUES (2, 'missing-commit', 'invalid', '2026-07-11T12:00:00+00:00')
                """
            )
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute(
                """
                INSERT INTO profile_observation_events (
                    id, operation_id, profile_version, canonical_order, action, category,
                    metric, confidence, observed_at, source, evidence_level,
                    confirmed_by, committed_at
                ) VALUES ('invalid-event', 'invalid-operation', 99, 0, 'assert',
                          'environment', 'family_rule', 0.5,
                          '2026-07-11T12:00:00+00:00', 'parent',
                          'parent_confirmed', 'parent-1',
                          '2026-07-11T12:00:00+00:00')
                """
            )
    assert ("calibration_commits", "commit_id", "id") in profile_version_fks
    assert all(table != "profile_versions" for table, _, _ in commit_fks)
    assert ("profile_versions", "profile_version", "profile_version") in observation_fks


@pytest.mark.parametrize(
    ("table", "column", "row_id"),
    [
        ("calibration_turn_receipts", "raw_text", "receipt-1"),
        ("calibration_drafts", "draft_digest", "draft-1"),
        ("calibration_commits", "confirmed_by", "commit-1"),
        ("profile_versions", "reason", 1),
        ("profile_observation_events", "confidence", "event-1"),
        ("school_brief_revisions", "raw_text", "school-1-r1"),
        ("calibration_checkpoints", "resume_stage", "checkpoint-1"),
        ("calibration_audit_events", "event_type", "audit-1"),
    ],
)
def test_every_family_history_table_rejects_update_and_delete(
    tmp_path: Path,
    table: str,
    column: str,
    row_id: str | int,
) -> None:
    database_path = tmp_path / f"append-only-{table}.db"
    run_migrations(database_path)
    primary_key = "profile_version" if table == "profile_versions" else "id"
    with connect_database(database_path) as connection:
        _seed_family_immutable_rows(connection)
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                f'UPDATE "{table}" SET "{column}" = "{column}" WHERE "{primary_key}" = ?',
                (row_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                f'DELETE FROM "{table}" WHERE "{primary_key}" = ?',
                (row_id,),
            )
