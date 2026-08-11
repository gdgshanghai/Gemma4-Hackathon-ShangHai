"""Transactional persistence for native-function-calling request traces."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from backend.contracts.models import (
    HarnessTrace,
    HarnessTraceEvent,
    HarnessTraceRecord,
    LLMRun,
    ToolRun,
)
from backend.errors import NotFoundError
from backend.storage.database import connect_database


RunStatus = Literal["completed", "failed"]
_SAFE_GENERATION_PARAMETERS = frozenset(
    {
        "tool_choice",
        "max_tokens",
        "exposed_tools",
        "temperature",
        "top_p",
        "seed",
    }
)


class RunTraceRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        connection = connect_database(self.database_path)
        try:
            yield connection
        finally:
            connection.close()

    def start_trace(self, trace: HarnessTrace) -> HarnessTrace:
        if trace.status != "started" or trace.completed_at is not None:
            raise ValueError("a new trace must be started and incomplete")
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO harness_traces (
                    id, trace_id, session_id, workflow_phase, actor, role,
                    expected_version, caller_idempotency_sha256, harness_version,
                    status, final_error_code, started_at, completed_at,
                    model_calls, tool_rounds, handler_executions, cache_hits,
                    schema_repair_used
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace.id,
                    trace.trace_id,
                    trace.session_id,
                    trace.workflow_phase,
                    trace.actor,
                    trace.role,
                    trace.expected_version,
                    trace.caller_idempotency_sha256,
                    trace.harness_version,
                    trace.status,
                    trace.final_error_code,
                    _iso(trace.started_at),
                    None,
                    trace.model_calls,
                    trace.tool_rounds,
                    trace.handler_executions,
                    trace.cache_hits,
                    int(trace.schema_repair_used),
                ),
            )
        return trace

    def finalize_trace(
        self,
        trace_id: str,
        *,
        status: RunStatus,
        final_error_code: str | None,
        completed_at: datetime,
        model_calls: int,
        tool_rounds: int,
        handler_executions: int,
        cache_hits: int,
        schema_repair_used: bool,
    ) -> HarnessTrace:
        if status == "completed" and final_error_code is not None:
            raise ValueError("a completed trace cannot have a final error")
        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE harness_traces
                SET status = ?, final_error_code = ?, completed_at = ?,
                    model_calls = ?, tool_rounds = ?, handler_executions = ?,
                    cache_hits = ?, schema_repair_used = ?
                WHERE trace_id = ? AND status = 'started'
                """,
                (
                    status,
                    final_error_code,
                    _iso(completed_at),
                    model_calls,
                    tool_rounds,
                    handler_executions,
                    cache_hits,
                    int(schema_repair_used),
                    trace_id,
                ),
            )
            if cursor.rowcount != 1:
                raise NotFoundError("started harness trace", trace_id)
            row = _require_row(
                connection.execute(
                    "SELECT * FROM harness_traces WHERE trace_id = ?", (trace_id,)
                ).fetchone(),
                "harness trace",
                trace_id,
            )
        return _trace_from_row(row)

    def start_llm_run(
        self,
        *,
        trace_id: str,
        run_id: str,
        session_id: str | None,
        model: str,
        request_sha256: str,
        generation_parameters: Mapping[str, Any],
        started_at: datetime,
    ) -> LLMRun:
        unsafe_parameters = set(generation_parameters) - _SAFE_GENERATION_PARAMETERS
        if unsafe_parameters:
            raise ValueError("unsupported or unsafe generation parameter")
        parameters_json = _encode_object(generation_parameters)
        with self._transaction() as connection:
            ordinal = _next_kind_ordinal(connection, "llm_runs", trace_id)
            event_ordinal = _next_event_ordinal(connection, trace_id)
            connection.execute(
                """
                INSERT INTO llm_runs (
                    id, trace_id, ordinal, session_id, model, request_sha256,
                    generation_parameters_json, response_json, finish_reason,
                    status, error_code, started_at, completed_at, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, 'started', NULL, ?, NULL, NULL)
                """,
                (
                    run_id,
                    trace_id,
                    ordinal,
                    session_id,
                    model,
                    request_sha256,
                    parameters_json,
                    _iso(started_at),
                ),
            )
            _insert_event(
                connection,
                trace_id=trace_id,
                ordinal=event_ordinal,
                event_kind="llm",
                run_id=run_id,
                created_at=started_at,
            )
            row = connection.execute(
                "SELECT * FROM llm_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return _llm_from_row(_require_row(row, "LLM run", run_id))

    def complete_llm_run(
        self,
        run_id: str,
        *,
        response: Mapping[str, Any],
        finish_reason: str,
        completed_at: datetime,
        latency_ms: int,
    ) -> LLMRun:
        return self._finish_llm_run(
            run_id,
            status="completed",
            response_json=_encode_object(response),
            finish_reason=finish_reason,
            error_code=None,
            completed_at=completed_at,
            latency_ms=latency_ms,
        )

    def fail_llm_run(
        self,
        run_id: str,
        *,
        error_code: str,
        completed_at: datetime,
        latency_ms: int,
    ) -> LLMRun:
        return self._finish_llm_run(
            run_id,
            status="failed",
            response_json=None,
            finish_reason=None,
            error_code=error_code,
            completed_at=completed_at,
            latency_ms=latency_ms,
        )

    def _finish_llm_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        response_json: str | None,
        finish_reason: str | None,
        error_code: str | None,
        completed_at: datetime,
        latency_ms: int,
    ) -> LLMRun:
        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE llm_runs
                SET response_json = ?, finish_reason = ?, status = ?,
                    error_code = ?, completed_at = ?, latency_ms = ?
                WHERE id = ? AND status = 'started'
                """,
                (
                    response_json,
                    finish_reason,
                    status,
                    error_code,
                    _iso(completed_at),
                    latency_ms,
                    run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise NotFoundError("started LLM run", run_id)
            row = connection.execute(
                "SELECT * FROM llm_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return _llm_from_row(_require_row(row, "LLM run", run_id))

    def start_tool_run(
        self,
        *,
        trace_id: str,
        run_id: str,
        session_id: str | None,
        llm_run_id: str | None,
        tool_name: str,
        call_id: str,
        arguments: Mapping[str, Any],
        cache_hit: bool,
        handler_executed: bool,
        started_at: datetime,
    ) -> ToolRun:
        arguments_json = _encode_object(arguments)
        with self._transaction() as connection:
            ordinal = _next_kind_ordinal(connection, "tool_runs", trace_id)
            event_ordinal = _next_event_ordinal(connection, trace_id)
            connection.execute(
                """
                INSERT INTO tool_runs (
                    id, trace_id, ordinal, session_id, llm_run_id, tool_name,
                    call_id, arguments_json, result_json, cache_hit,
                    handler_executed, status, error_code, started_at,
                    completed_at, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, 'started', NULL, ?, NULL, NULL)
                """,
                (
                    run_id,
                    trace_id,
                    ordinal,
                    session_id,
                    llm_run_id,
                    tool_name,
                    call_id,
                    arguments_json,
                    int(cache_hit),
                    int(handler_executed),
                    _iso(started_at),
                ),
            )
            _insert_event(
                connection,
                trace_id=trace_id,
                ordinal=event_ordinal,
                event_kind="tool",
                run_id=run_id,
                created_at=started_at,
            )
            row = connection.execute(
                "SELECT * FROM tool_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return _tool_from_row(_require_row(row, "tool run", run_id))

    def complete_tool_run(
        self,
        run_id: str,
        *,
        result: Mapping[str, Any],
        completed_at: datetime,
        latency_ms: int,
    ) -> ToolRun:
        return self._finish_tool_run(
            run_id,
            status="completed",
            result_json=_encode_object(result),
            error_code=None,
            completed_at=completed_at,
            latency_ms=latency_ms,
        )

    def fail_tool_run(
        self,
        run_id: str,
        *,
        error_code: str,
        result: Mapping[str, Any] | None = None,
        completed_at: datetime,
        latency_ms: int,
    ) -> ToolRun:
        return self._finish_tool_run(
            run_id,
            status="failed",
            result_json=_encode_object(result) if result is not None else None,
            error_code=error_code,
            completed_at=completed_at,
            latency_ms=latency_ms,
        )

    def _finish_tool_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        result_json: str | None,
        error_code: str | None,
        completed_at: datetime,
        latency_ms: int,
    ) -> ToolRun:
        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE tool_runs
                SET result_json = ?, status = ?, error_code = ?,
                    completed_at = ?, latency_ms = ?
                WHERE id = ? AND status = 'started'
                """,
                (
                    result_json,
                    status,
                    error_code,
                    _iso(completed_at),
                    latency_ms,
                    run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise NotFoundError("started tool run", run_id)
            row = connection.execute(
                "SELECT * FROM tool_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return _tool_from_row(_require_row(row, "tool run", run_id))

    def get_trace(self, trace_id: str) -> HarnessTraceRecord:
        with self._read_connection() as connection:
            trace_row = connection.execute(
                "SELECT * FROM harness_traces WHERE trace_id = ?", (trace_id,)
            ).fetchone()
            if trace_row is None:
                raise NotFoundError("harness trace", trace_id)
            event_rows = connection.execute(
                """
                SELECT * FROM harness_trace_events
                WHERE trace_id = ? ORDER BY ordinal
                """,
                (trace_id,),
            ).fetchall()
            llm_rows = connection.execute(
                "SELECT * FROM llm_runs WHERE trace_id = ? ORDER BY ordinal",
                (trace_id,),
            ).fetchall()
            tool_rows = connection.execute(
                "SELECT * FROM tool_runs WHERE trace_id = ? ORDER BY ordinal",
                (trace_id,),
            ).fetchall()
        return HarnessTraceRecord(
            trace=_trace_from_row(trace_row),
            events=tuple(_event_from_row(row) for row in event_rows),
            llm_runs=tuple(_llm_from_row(row) for row in llm_rows),
            tool_runs=tuple(_tool_from_row(row) for row in tool_rows),
        )


def _next_kind_ordinal(
    connection: sqlite3.Connection, table: str, trace_id: str
) -> int:
    if table not in {"llm_runs", "tool_runs"}:
        raise ValueError("invalid trace run table")
    return int(
        connection.execute(
            f"SELECT COALESCE(MAX(ordinal), 0) + 1 FROM {table} WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()[0]
    )


def _next_event_ordinal(connection: sqlite3.Connection, trace_id: str) -> int:
    return int(
        connection.execute(
            """
            SELECT COALESCE(MAX(ordinal), 0) + 1
            FROM harness_trace_events WHERE trace_id = ?
            """,
            (trace_id,),
        ).fetchone()[0]
    )


def _insert_event(
    connection: sqlite3.Connection,
    *,
    trace_id: str,
    ordinal: int,
    event_kind: Literal["llm", "tool"],
    run_id: str,
    created_at: datetime,
) -> None:
    connection.execute(
        """
        INSERT INTO harness_trace_events (
            id, trace_id, ordinal, event_kind, llm_run_id, tool_run_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"{trace_id}:event:{ordinal}",
            trace_id,
            ordinal,
            event_kind,
            run_id if event_kind == "llm" else None,
            run_id if event_kind == "tool" else None,
            _iso(created_at),
        ),
    )


def _trace_from_row(row: sqlite3.Row) -> HarnessTrace:
    return HarnessTrace(
        id=str(row["id"]),
        trace_id=str(row["trace_id"]),
        session_id=str(row["session_id"]) if row["session_id"] is not None else None,
        workflow_phase=str(row["workflow_phase"]),
        actor=str(row["actor"]),
        role=str(row["role"]),
        expected_version=int(row["expected_version"]),
        caller_idempotency_sha256=(
            str(row["caller_idempotency_sha256"])
            if row["caller_idempotency_sha256"] is not None
            else None
        ),
        harness_version=str(row["harness_version"]),
        status=str(row["status"]),
        final_error_code=(
            str(row["final_error_code"])
            if row["final_error_code"] is not None
            else None
        ),
        started_at=datetime.fromisoformat(str(row["started_at"])),
        completed_at=(
            datetime.fromisoformat(str(row["completed_at"]))
            if row["completed_at"] is not None
            else None
        ),
        model_calls=int(row["model_calls"]),
        tool_rounds=int(row["tool_rounds"]),
        handler_executions=int(row["handler_executions"]),
        cache_hits=int(row["cache_hits"]),
        schema_repair_used=bool(row["schema_repair_used"]),
    )


def _llm_from_row(row: sqlite3.Row) -> LLMRun:
    return LLMRun(
        id=str(row["id"]),
        trace_id=str(row["trace_id"]),
        ordinal=int(row["ordinal"]),
        session_id=str(row["session_id"]) if row["session_id"] is not None else None,
        model=str(row["model"]),
        request_sha256=str(row["request_sha256"]),
        generation_parameters=_decode_object(str(row["generation_parameters_json"])),
        response=(
            _decode_object(str(row["response_json"]))
            if row["response_json"] is not None
            else None
        ),
        finish_reason=(
            str(row["finish_reason"]) if row["finish_reason"] is not None else None
        ),
        status=str(row["status"]),
        error_code=str(row["error_code"]) if row["error_code"] is not None else None,
        started_at=datetime.fromisoformat(str(row["started_at"])),
        completed_at=(
            datetime.fromisoformat(str(row["completed_at"]))
            if row["completed_at"] is not None
            else None
        ),
        latency_ms=int(row["latency_ms"]) if row["latency_ms"] is not None else None,
    )


def _tool_from_row(row: sqlite3.Row) -> ToolRun:
    return ToolRun(
        id=str(row["id"]),
        trace_id=str(row["trace_id"]),
        ordinal=int(row["ordinal"]),
        session_id=str(row["session_id"]) if row["session_id"] is not None else None,
        llm_run_id=(
            str(row["llm_run_id"]) if row["llm_run_id"] is not None else None
        ),
        tool_name=str(row["tool_name"]),
        call_id=str(row["call_id"]),
        arguments=_decode_object(str(row["arguments_json"])),
        result=(
            _decode_object(str(row["result_json"]))
            if row["result_json"] is not None
            else None
        ),
        cache_hit=bool(row["cache_hit"]),
        handler_executed=bool(row["handler_executed"]),
        status=str(row["status"]),
        error_code=str(row["error_code"]) if row["error_code"] is not None else None,
        started_at=datetime.fromisoformat(str(row["started_at"])),
        completed_at=(
            datetime.fromisoformat(str(row["completed_at"]))
            if row["completed_at"] is not None
            else None
        ),
        latency_ms=int(row["latency_ms"]) if row["latency_ms"] is not None else None,
    )


def _event_from_row(row: sqlite3.Row) -> HarnessTraceEvent:
    return HarnessTraceEvent(
        id=str(row["id"]),
        trace_id=str(row["trace_id"]),
        ordinal=int(row["ordinal"]),
        event_kind=str(row["event_kind"]),
        llm_run_id=(
            str(row["llm_run_id"]) if row["llm_run_id"] is not None else None
        ),
        tool_run_id=(
            str(row["tool_run_id"]) if row["tool_run_id"] is not None else None
        ),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _encode_object(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _decode_object(value: str) -> dict[str, Any]:
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise ValueError("stored trace JSON must be an object")
    return decoded


def _iso(value: datetime) -> str:
    return value.isoformat()


def _require_row(
    row: sqlite3.Row | None, entity: str, entity_id: str
) -> sqlite3.Row:
    if row is None:
        raise NotFoundError(entity, entity_id)
    return row
