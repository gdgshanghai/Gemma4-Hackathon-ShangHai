from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.contracts.models import HarnessTrace
from backend.storage.database import connect_database, run_migrations
from backend.storage.run_traces import RunTraceRepository


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = PROJECT_ROOT / "backend" / "storage" / "migrations"


def _trace(trace_id: str = "trace-1", *, session_id: str | None = "session-1") -> HarnessTrace:
    return HarnessTrace(
        id=trace_id,
        trace_id=trace_id,
        session_id=session_id,
        workflow_phase="context_read",
        actor="child-1",
        role="child",
        expected_version=2,
        caller_idempotency_sha256=None,
        harness_version="native-fc-v1",
        status="started",
        final_error_code=None,
        started_at=NOW,
        completed_at=None,
        model_calls=0,
        tool_rounds=0,
        handler_executions=0,
        cache_hits=0,
        schema_repair_used=False,
    )


@pytest.fixture
def repository(tmp_path: Path) -> RunTraceRepository:
    database_path = tmp_path / "traces.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    return RunTraceRepository(database_path)


def test_start_complete_fail_and_ordered_retrieval(
    repository: RunTraceRepository,
) -> None:
    repository.start_trace(_trace())
    first_llm = repository.start_llm_run(
        trace_id="trace-1",
        run_id="llm-1",
        session_id="session-1",
        model="gemma-4-26b-a4b-it",
        request_sha256="a" * 64,
        generation_parameters={"tool_choice": "required", "max_tokens": 128},
        started_at=NOW,
    )
    completed_llm = repository.complete_llm_run(
        "llm-1",
        response={"choices": [{"finish_reason": "tool_calls"}]},
        finish_reason="tool_calls",
        completed_at=NOW + timedelta(milliseconds=20),
        latency_ms=20,
    )
    tool = repository.start_tool_run(
        trace_id="trace-1",
        run_id="tool-1",
        session_id="session-1",
        llm_run_id="llm-1",
        tool_name="get_planning_context",
        call_id="call-1",
        arguments={"topic": "tonight"},
        cache_hit=False,
        handler_executed=False,
        started_at=NOW + timedelta(milliseconds=21),
    )
    failed_tool = repository.fail_tool_run(
        "tool-1",
        error_code="tool_result_not_object",
        completed_at=NOW + timedelta(milliseconds=25),
        latency_ms=4,
    )
    repository.finalize_trace(
        "trace-1",
        status="failed",
        final_error_code="tool_result_not_object",
        completed_at=NOW + timedelta(milliseconds=26),
        model_calls=1,
        tool_rounds=1,
        handler_executions=1,
        cache_hits=0,
        schema_repair_used=False,
    )

    stored = repository.get_trace("trace-1")

    assert first_llm.ordinal == 1
    assert completed_llm.status == "completed"
    assert completed_llm.finish_reason == "tool_calls"
    assert tool.ordinal == 1
    assert failed_tool.status == "failed"
    assert failed_tool.error_code == "tool_result_not_object"
    assert stored.trace.status == "failed"
    assert stored.trace.final_error_code == "tool_result_not_object"
    assert [event.ordinal for event in stored.events] == [1, 2]
    assert [event.event_kind for event in stored.events] == ["llm", "tool"]
    assert stored.events[0].llm_run_id == "llm-1"
    assert stored.events[0].tool_run_id is None
    assert stored.events[1].tool_run_id == "tool-1"
    assert stored.events[1].llm_run_id is None


def test_request_hash_privacy_and_run_metadata(repository: RunTraceRepository) -> None:
    repository.start_trace(_trace())
    secret_prompt = "private child prompt"
    request_hash = "b" * 64
    repository.start_llm_run(
        trace_id="trace-1",
        run_id="llm-1",
        session_id="session-1",
        model="gemma-4-26b-a4b-it",
        request_sha256=request_hash,
        generation_parameters={"tool_choice": "none", "max_tokens": 32},
        started_at=NOW,
    )

    with connect_database(repository.database_path) as connection:
        row = connection.execute(
            "SELECT * FROM llm_runs WHERE id = 'llm-1'"
        ).fetchone()
        columns = {item[1] for item in connection.execute("PRAGMA table_info(llm_runs)")}

    assert row["request_sha256"] == request_hash
    assert row["generation_parameters_json"] == '{"max_tokens":32,"tool_choice":"none"}'
    assert not {"prompt", "messages", "request_json"} & columns
    assert secret_prompt not in str(dict(row))


@pytest.mark.parametrize("forbidden_key", ["messages", "prompt", "request_json"])
def test_generation_metadata_rejects_raw_request_fields(
    repository: RunTraceRepository, forbidden_key: str
) -> None:
    repository.start_trace(_trace())

    with pytest.raises(ValueError, match="generation parameter"):
        repository.start_llm_run(
            trace_id="trace-1",
            run_id="llm-unsafe",
            session_id="session-1",
            model="gemma-4-26b-a4b-it",
            request_sha256="b" * 64,
            generation_parameters={forbidden_key: "private child prompt"},
            started_at=NOW,
        )

    stored = repository.get_trace("trace-1")
    assert stored.llm_runs == ()
    assert stored.events == ()


def test_zero_call_failed_trace_is_persisted(repository: RunTraceRepository) -> None:
    repository.start_trace(_trace())

    repository.finalize_trace(
        "trace-1",
        status="failed",
        final_error_code="missing_idempotency_key",
        completed_at=NOW,
        model_calls=0,
        tool_rounds=0,
        handler_executions=0,
        cache_hits=0,
        schema_repair_used=False,
    )

    stored = repository.get_trace("trace-1")
    assert stored.trace.final_error_code == "missing_idempotency_key"
    assert stored.trace.model_calls == 0
    assert stored.events == ()
    assert stored.llm_runs == ()
    assert stored.tool_runs == ()


def test_shared_event_ordinals_are_gap_free_across_run_types(
    repository: RunTraceRepository,
) -> None:
    repository.start_trace(_trace())
    repository.start_llm_run(
        trace_id="trace-1",
        run_id="llm-1",
        session_id="session-1",
        model="gemma-4-26b-a4b-it",
        request_sha256="a" * 64,
        generation_parameters={"tool_choice": "required"},
        started_at=NOW,
    )
    repository.start_tool_run(
        trace_id="trace-1",
        run_id="tool-1",
        session_id="session-1",
        llm_run_id="llm-1",
        tool_name="get_planning_context",
        call_id="call-1",
        arguments={"topic": "tonight"},
        cache_hit=True,
        handler_executed=False,
        started_at=NOW,
    )
    repository.start_llm_run(
        trace_id="trace-1",
        run_id="llm-2",
        session_id="session-1",
        model="gemma-4-26b-a4b-it",
        request_sha256="c" * 64,
        generation_parameters={"tool_choice": "auto"},
        started_at=NOW,
    )

    stored = repository.get_trace("trace-1")

    assert [event.ordinal for event in stored.events] == [1, 2, 3]
    assert [run.ordinal for run in stored.llm_runs] == [1, 2]
    assert [run.ordinal for run in stored.tool_runs] == [1]
    assert stored.tool_runs[0].cache_hit is True
    assert stored.tool_runs[0].handler_executed is False


def test_concurrent_trace_ids_keep_independent_ordinals(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "concurrent.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")

    def create(index: int) -> tuple[str, int]:
        trace_id = f"trace-{index}"
        repository = RunTraceRepository(database_path)
        repository.start_trace(_trace(trace_id, session_id=None))
        run = repository.start_llm_run(
            trace_id=trace_id,
            run_id=f"llm-{index}",
            session_id=None,
            model="gemma-4-26b-a4b-it",
            request_sha256=f"{index:064x}",
            generation_parameters={"tool_choice": "none"},
            started_at=NOW,
        )
        event = repository.get_trace(trace_id).events[0]
        return run.trace_id, event.ordinal

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(create, range(8)))

    assert results == [(f"trace-{index}", 1) for index in range(8)]


def test_migration_deterministically_backfills_linked_and_orphan_runs(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy.db"
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    for name in ("0001_initial.sql", "0002_task_planning_fields.sql"):
        shutil.copy2(MIGRATIONS / name, migrations / name)
    assert run_migrations(database_path, migrations_dir=migrations) == [1, 2]
    with connect_database(database_path) as connection:
        connection.execute(
            """
            INSERT INTO llm_runs (
                id, model, request_sha256, response_json, status,
                started_at, completed_at, latency_ms
            ) VALUES ('llm-old', 'gemma-4-26b-a4b-it', ?, '{}', 'completed',
                      '2026-07-11T12:00:00+00:00',
                      '2026-07-11T12:00:01+00:00', 1000)
            """,
            ("d" * 64,),
        )
        connection.execute(
            """
            INSERT INTO tool_runs (
                id, llm_run_id, tool_name, call_id, arguments_json,
                result_json, status, started_at, completed_at, latency_ms
            ) VALUES ('tool-linked', 'llm-old', 'get_planning_context',
                      'call-linked', '{}', '{}', 'completed',
                      '2026-07-11T12:00:00.5+00:00',
                      '2026-07-11T12:00:00.6+00:00', 100)
            """
        )
        connection.execute(
            """
            INSERT INTO tool_runs (
                id, llm_run_id, tool_name, call_id, arguments_json,
                result_json, status, started_at, completed_at, latency_ms
            ) VALUES ('tool-orphan', NULL, 'get_planning_context',
                      'call-orphan', '{}', '{}', 'completed',
                      '2026-07-11T11:00:00+00:00',
                      '2026-07-11T11:00:01+00:00', 1000)
            """
        )
        connection.commit()
    shutil.copy2(MIGRATIONS / "0003_harness_traces.sql", migrations)

    assert run_migrations(database_path, migrations_dir=migrations) == [3]
    assert run_migrations(database_path, migrations_dir=migrations) == []

    with connect_database(database_path) as connection:
        llm = connection.execute(
            "SELECT id, trace_id, response_json FROM llm_runs"
        ).fetchone()
        tools = connection.execute(
            "SELECT id, trace_id, result_json FROM tool_runs ORDER BY id"
        ).fetchall()
        traces = connection.execute(
            """
            SELECT trace_id, completed_at
            FROM harness_traces
            ORDER BY trace_id
            """
        ).fetchall()
        events = connection.execute(
            """
            SELECT trace_id, ordinal, event_kind, llm_run_id, tool_run_id
            FROM harness_trace_events
            ORDER BY trace_id, ordinal
            """
        ).fetchall()
        llm_trace_not_null = next(
            row[3] for row in connection.execute("PRAGMA table_info(llm_runs)")
            if row[1] == "trace_id"
        )
        tool_trace_not_null = next(
            row[3] for row in connection.execute("PRAGMA table_info(tool_runs)")
            if row[1] == "trace_id"
        )

    assert tuple(llm) == ("llm-old", "legacy-llm-llm-old", "{}")
    assert [tuple(row) for row in tools] == [
        ("tool-linked", "legacy-llm-llm-old", "{}"),
        ("tool-orphan", "legacy-tool-tool-orphan", "{}"),
    ]
    assert [tuple(row) for row in traces] == [
        ("legacy-llm-llm-old", "2026-07-11T12:00:01+00:00"),
        ("legacy-tool-tool-orphan", "2026-07-11T11:00:01+00:00"),
    ]
    assert [tuple(row) for row in events] == [
        ("legacy-llm-llm-old", 1, "llm", "llm-old", None),
        ("legacy-llm-llm-old", 2, "tool", None, "tool-linked"),
        ("legacy-tool-tool-orphan", 1, "tool", None, "tool-orphan"),
    ]
    assert llm_trace_not_null == 1
    assert tool_trace_not_null == 1
