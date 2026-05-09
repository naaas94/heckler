"""SQLite persistence for heckler structured events (stdlib ``sqlite3`` only).

Call :func:`open_store`, then :func:`init_schema` once per database file, then
:func:`insert_event_row` for each event. Payload and correlation are stored as JSON **text**
(UTF-8); callers pass already-serialized strings (e.g. ``json.dumps``).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Bump when DDL changes require migration logic (see ``.dev/decision-logs/T12.md``).
SCHEMA_VERSION: int = 1


def _configure_connection(conn: sqlite3.Connection) -> None:
    """Apply WAL and safety pragmas for single-process, multi-threaded use."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")


def open_store(path: Path) -> sqlite3.Connection:
    """Open or create a SQLite database at ``path`` with WAL journaling enabled.

    Creates parent directories. Uses ``check_same_thread=False`` and a busy timeout so a
    shared connection can be used from the pipeline reaction worker (see T12). Serialized
    writes should still use an application lock if multiple threads insert concurrently.
    """
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(resolved),
        timeout=30.0,
        check_same_thread=False,
    )
    _configure_connection(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create schema tables and record ``SCHEMA_VERSION``.

    Raises ``RuntimeError`` if an existing database reports an unsupported version.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS heckler_schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            payload_json TEXT NOT NULL,
            correlation_json TEXT
        )
        """
    )
    row = conn.execute(
        "SELECT version FROM heckler_schema_version WHERE id = 1"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO heckler_schema_version (id, version) VALUES (1, ?)",
            (SCHEMA_VERSION,),
        )
    elif int(row[0]) != SCHEMA_VERSION:
        raise RuntimeError(
            f"unsupported heckler schema version {row[0]}, expected {SCHEMA_VERSION}"
        )
    conn.commit()


def insert_event_row(
    conn_or_cursor: sqlite3.Connection | sqlite3.Cursor,
    payload_json: str,
    correlation_json: str | None = None,
) -> int:
    """Insert one event row; returns SQLite ``rowid``.

    If ``conn_or_cursor`` is a :class:`sqlite3.Connection`, the insert is committed.
    If it is a :class:`sqlite3.Cursor`, the caller owns the transaction (commit/rollback).
    """
    sql = "INSERT INTO events (payload_json, correlation_json) VALUES (?, ?)"
    params = (payload_json, correlation_json)

    if isinstance(conn_or_cursor, sqlite3.Connection):
        cur = conn_or_cursor.execute(sql, params)
        rowid = int(cur.lastrowid)
        conn_or_cursor.commit()
        return rowid

    conn_or_cursor.execute(sql, params)
    return int(conn_or_cursor.lastrowid)
