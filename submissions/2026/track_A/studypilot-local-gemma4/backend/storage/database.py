"""SQLite connection configuration and checksum-verified migrations."""

from __future__ import annotations

import hashlib
import re
import sqlite3
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MIGRATIONS_DIR = Path(__file__).with_name("migrations")
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "data" / "local" / "backups"
BUSY_TIMEOUT_MS = 5_000
_MIGRATION_PATTERN = re.compile(r"^(?P<version>\d{4})_(?P<name>[a-z0-9_]+)\.sql$")


class MigrationError(RuntimeError):
    """Base class for migration failures."""


class MigrationChecksumError(MigrationError):
    """Raised when an applied migration no longer matches its source file."""


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str


def connect_database(
    database_path: str | Path,
    *,
    busy_timeout_ms: int = BUSY_TIMEOUT_MS,
) -> sqlite3.Connection:
    """Open a consistently configured SQLite connection."""
    path = Path(database_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            path,
            timeout=busy_timeout_ms / 1_000,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms:d}")
        connection.execute("PRAGMA foreign_keys = ON")
        _enable_wal(connection, busy_timeout_ms)
        return connection
    except Exception:
        if connection is not None:
            connection.close()
        raise


def _enable_wal(
    connection: sqlite3.Connection,
    busy_timeout_ms: int,
) -> None:
    deadline = time.monotonic() + (busy_timeout_ms / 1_000)
    while True:
        try:
            row = connection.execute("PRAGMA journal_mode = WAL").fetchone()
            if row is None or str(row[0]).lower() != "wal":
                raise sqlite3.OperationalError("failed to enable WAL journal mode")
            return
        except sqlite3.OperationalError as error:
            if "locked" not in str(error).lower() or time.monotonic() >= deadline:
                raise
            time.sleep(0.01)


def run_migrations(
    database_path: str | Path,
    *,
    migrations_dir: str | Path = DEFAULT_MIGRATIONS_DIR,
    backup_dir: str | Path | None = None,
) -> list[int]:
    """Verify migration history and apply each pending migration once."""
    path = Path(database_path).expanduser().resolve()
    migrations = _discover_migrations(Path(migrations_dir))
    connection = connect_database(path)
    backup_created = False
    try:
        while True:
            try:
                connection.execute("BEGIN IMMEDIATE")
                _ensure_history_table(connection)
                applied = _load_applied_migrations(connection)
                _verify_applied_migrations(migrations, applied)
                pending = [
                    migration
                    for migration in migrations
                    if migration.version not in applied
                ]
                needs_backup = (
                    not backup_created
                    and any(migration.version > 1 for migration in pending)
                    and _has_application_data(connection)
                )
                if needs_backup:
                    connection.rollback()
                    _backup_database(
                        connection,
                        path,
                        (
                            Path(backup_dir)
                            if backup_dir is not None
                            else DEFAULT_BACKUP_DIR
                        ),
                    )
                    backup_created = True
                    continue

                for migration in pending:
                    _apply_migration(connection, migration)
                connection.commit()
                return [migration.version for migration in pending]
            except Exception:
                if connection.in_transaction:
                    connection.rollback()
                raise
    finally:
        connection.close()


def _discover_migrations(migrations_dir: Path) -> list[Migration]:
    directory = migrations_dir.expanduser().resolve()
    if not directory.is_dir():
        raise MigrationError(f"migration directory does not exist: {directory}")

    migrations: list[Migration] = []
    seen_versions: set[int] = set()
    for path in sorted(directory.glob("*.sql")):
        match = _MIGRATION_PATTERN.fullmatch(path.name)
        if match is None:
            raise MigrationError(f"invalid migration filename: {path.name}")
        version = int(match.group("version"))
        if version in seen_versions:
            raise MigrationError(f"duplicate migration version {version}")
        seen_versions.add(version)
        migrations.append(
            Migration(
                version=version,
                name=match.group("name"),
                path=path,
                checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    return migrations


def _ensure_history_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL CHECK (length(checksum) = 64),
            applied_at TEXT NOT NULL
                DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )
        """
    )


def _load_applied_migrations(
    connection: sqlite3.Connection,
) -> dict[int, sqlite3.Row]:
    return {
        int(row["version"]): row
        for row in connection.execute(
            "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
        )
    }


def _verify_applied_migrations(
    migrations: list[Migration],
    applied: dict[int, sqlite3.Row],
) -> None:
    available = {migration.version: migration for migration in migrations}
    for version, row in applied.items():
        migration = available.get(version)
        if migration is None:
            raise MigrationError(f"applied migration version {version} is missing")
        if row["checksum"] != migration.checksum:
            raise MigrationChecksumError(
                f"checksum mismatch for migration version {version}"
            )
        if row["name"] != migration.name:
            raise MigrationError(f"name mismatch for migration version {version}")


def _has_application_data(connection: sqlite3.Connection) -> bool:
    tables = [
        str(row["name"])
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_schema
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
              AND name <> 'schema_migrations'
            ORDER BY name
            """
        )
    ]
    return any(
        connection.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone()
        is not None
        for table in tables
    )


def _backup_database(
    connection: sqlite3.Connection,
    database_path: Path,
    backup_dir: Path,
) -> Path:
    directory = backup_dir.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = directory / f"{database_path.stem}-{timestamp}.db"
    backup = sqlite3.connect(backup_path)
    try:
        connection.backup(backup)
    finally:
        backup.close()
    return backup_path


def _apply_migration(connection: sqlite3.Connection, migration: Migration) -> None:
    applied_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    for statement in _iter_sql_statements(
        migration.path.read_text(encoding="utf-8")
    ):
        connection.execute(statement)
    connection.execute(
        """
        INSERT INTO schema_migrations (version, name, checksum, applied_at)
        VALUES (?, ?, ?, ?)
        """,
        (migration.version, migration.name, migration.checksum, applied_at),
    )


def _iter_sql_statements(script: str) -> Iterator[str]:
    buffer: list[str] = []
    for character in script:
        buffer.append(character)
        if character == ";" and sqlite3.complete_statement("".join(buffer)):
            statement = "".join(buffer).strip()
            if statement:
                yield statement
            buffer.clear()
    remainder = "".join(buffer).strip()
    if remainder:
        yield remainder
