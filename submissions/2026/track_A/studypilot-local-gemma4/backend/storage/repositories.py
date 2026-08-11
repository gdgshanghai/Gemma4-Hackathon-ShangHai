"""Transactional repositories for the V13 foundation entities."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, time
from pathlib import Path
from typing import Any

from backend.contracts.models import (
    EveningSession,
    ObservationEvent,
    SchoolBrief,
    SessionStage,
    Source,
)
from backend.errors import IdempotencyConflictError, NotFoundError, VersionConflictError
from backend.storage.database import connect_database


JsonObject = dict[str, Any]


class _Repository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        connection = connect_database(self.database_path)
        try:
            yield connection
        finally:
            connection.close()

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


class SchoolBriefRepository(_Repository):
    def create(self, brief: SchoolBrief) -> SchoolBrief:
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO school_briefs (
                    id,
                    brief_date,
                    source_path,
                    content_sha256,
                    raw_text,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    brief.id,
                    brief.brief_date.isoformat(),
                    brief.source_path,
                    brief.content_sha256,
                    brief.raw_text,
                    brief.created_at.isoformat(),
                ),
            )
        return brief

    def get(self, brief_id: str) -> SchoolBrief:
        with self._read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM school_briefs WHERE id = ?",
                (brief_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError("school brief", brief_id)
        return _school_brief_from_row(row)


class EveningSessionRepository(_Repository):
    def create(self, session: EveningSession) -> EveningSession:
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO evening_sessions (
                    id,
                    session_date,
                    timezone,
                    sleep_time,
                    stage,
                    version,
                    available_minutes,
                    school_brief_id,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.session_date.isoformat(),
                    session.timezone,
                    session.sleep_time.isoformat(),
                    session.stage.value,
                    session.version,
                    session.available_minutes,
                    session.school_brief_id,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )
        return session

    def get(self, session_id: str) -> EveningSession:
        with self._read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM evening_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError("evening session", session_id)
        return _evening_session_from_row(row)

    def advance_version(
        self,
        session_id: str,
        *,
        expected_version: int,
        new_stage: SessionStage,
    ) -> EveningSession:
        stage = SessionStage(new_stage)
        updated_at = datetime.now().astimezone().isoformat()
        with self._transaction() as connection:
            result = connection.execute(
                """
                UPDATE evening_sessions
                SET version = version + 1,
                    stage = ?,
                    updated_at = ?
                WHERE id = ? AND version = ?
                """,
                (stage.value, updated_at, session_id, expected_version),
            )
            if result.rowcount != 1:
                current = connection.execute(
                    "SELECT version FROM evening_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                if current is None:
                    raise NotFoundError("evening session", session_id)
                raise VersionConflictError(
                    "evening session",
                    session_id,
                    expected_version,
                    int(current["version"]),
                )
            row = connection.execute(
                "SELECT * FROM evening_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:  # pragma: no cover - guarded by the successful update
            raise NotFoundError("evening session", session_id)
        return _evening_session_from_row(row)


class EventRepository(_Repository):
    def append_observation(self, event: ObservationEvent) -> ObservationEvent:
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO observation_events (
                    id,
                    session_id,
                    event_type,
                    source,
                    payload_json,
                    occurred_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.session_id,
                    event.event_type,
                    event.source.value,
                    _encode_json(event.payload),
                    event.occurred_at.isoformat(),
                    event.created_at.isoformat(),
                ),
            )
        return event

    def list_observations(self, session_id: str) -> list[ObservationEvent]:
        with self._read_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM observation_events
                WHERE session_id = ?
                ORDER BY occurred_at, created_at, id
                """,
                (session_id,),
            ).fetchall()
        return [_observation_from_row(row) for row in rows]

    def append_audit(
        self,
        *,
        event_id: str,
        session_id: str | None,
        event_type: str,
        actor_source: Source,
        payload: Mapping[str, Any],
        trace_id: str,
        occurred_at: datetime,
    ) -> JsonObject:
        source = Source(actor_source)
        normalized_payload = dict(payload)
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    id,
                    session_id,
                    event_type,
                    actor_source,
                    payload_json,
                    trace_id,
                    occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    session_id,
                    event_type,
                    source.value,
                    _encode_json(normalized_payload),
                    trace_id,
                    occurred_at.isoformat(),
                ),
            )
        return {
            "event_id": event_id,
            "session_id": session_id,
            "event_type": event_type,
            "actor_source": source.value,
            "payload": normalized_payload,
            "trace_id": trace_id,
            "occurred_at": occurred_at.isoformat(),
        }


class IdempotencyRepository(_Repository):
    def lookup(
        self,
        operation: str,
        idempotency_key: str,
        request_hash: str,
    ) -> JsonObject | None:
        with self._read_connection() as connection:
            row = connection.execute(
                """
                SELECT request_hash, response_json
                FROM idempotency_records
                WHERE operation = ? AND idempotency_key = ?
                """,
                (operation, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        _verify_request_hash(row, operation, idempotency_key, request_hash)
        return _decode_json_object(str(row["response_json"]))

    def store(
        self,
        operation: str,
        idempotency_key: str,
        request_hash: str,
        response: Mapping[str, Any],
    ) -> JsonObject:
        response_json = _encode_json(dict(response))
        with self._transaction() as connection:
            existing = connection.execute(
                """
                SELECT request_hash, response_json
                FROM idempotency_records
                WHERE operation = ? AND idempotency_key = ?
                """,
                (operation, idempotency_key),
            ).fetchone()
            if existing is not None:
                _verify_request_hash(
                    existing,
                    operation,
                    idempotency_key,
                    request_hash,
                )
                return _decode_json_object(str(existing["response_json"]))
            connection.execute(
                """
                INSERT INTO idempotency_records (
                    operation,
                    idempotency_key,
                    request_hash,
                    response_json
                ) VALUES (?, ?, ?, ?)
                """,
                (operation, idempotency_key, request_hash, response_json),
            )
        return _decode_json_object(response_json)


def _school_brief_from_row(row: sqlite3.Row) -> SchoolBrief:
    return SchoolBrief(
        id=str(row["id"]),
        brief_date=datetime.fromisoformat(str(row["brief_date"])).date(),
        source_path=str(row["source_path"]),
        content_sha256=str(row["content_sha256"]),
        raw_text=str(row["raw_text"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _evening_session_from_row(row: sqlite3.Row) -> EveningSession:
    return EveningSession(
        id=str(row["id"]),
        session_date=datetime.fromisoformat(str(row["session_date"])).date(),
        timezone=str(row["timezone"]),
        sleep_time=time.fromisoformat(str(row["sleep_time"])),
        stage=SessionStage(str(row["stage"])),
        version=int(row["version"]),
        available_minutes=int(row["available_minutes"]),
        school_brief_id=(
            str(row["school_brief_id"])
            if row["school_brief_id"] is not None
            else None
        ),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )


def _observation_from_row(row: sqlite3.Row) -> ObservationEvent:
    return ObservationEvent(
        id=str(row["id"]),
        session_id=str(row["session_id"]) if row["session_id"] is not None else None,
        event_type=str(row["event_type"]),
        source=Source(str(row["source"])),
        payload=_decode_json_object(str(row["payload_json"])),
        occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _verify_request_hash(
    row: sqlite3.Row,
    operation: str,
    idempotency_key: str,
    request_hash: str,
) -> None:
    if row["request_hash"] != request_hash:
        raise IdempotencyConflictError(operation, idempotency_key)


def _encode_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _decode_json_object(value: str) -> JsonObject:
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise ValueError("stored JSON response must be an object")
    return decoded
