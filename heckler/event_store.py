"""SQLite persistence for heckler structured events (stdlib ``sqlite3`` only).

Call :func:`open_store`, then :func:`init_schema` once per database file, then
:func:`insert_event_row` (JSON-only rows) or :func:`insert_heckle_event_row` (live logger path:
JSON plus normalized columns and optional ``event_reactor_results`` in one transaction).
Payload and correlation are stored as JSON **text**
(UTF-8); callers pass already-serialized strings (e.g. ``json.dumps``).

Schema version **2** adds normalized ``events`` columns (mirroring :class:`~heckler.models.HeckleEvent`
fields except nested reactor data), a child table ``event_reactor_results`` for reactor payloads,
and ``heckler_eval_labels`` for dataset-style evaluation metadata. Legacy ``payload_json`` remains
written for round-trip/import compatibility until a later subtask moves writers to normalized
columns; analytics should prefer normalized columns and child tables once populated.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from heckler.models import HeckleEvent

logger = logging.getLogger(__name__)

# Bump when DDL changes require migration logic (see ``.dev/decision-logs/T12.md``, T21).
SCHEMA_VERSION: int = 2

# Normalized ``events`` columns (HeckleEvent scalars / optional fields). Types are SQLite affinities.
_EVENT_ANALYTICS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("utterance_id", "TEXT"),
    ("timestamp_iso", "TEXT"),
    ("transcript", "TEXT"),
    ("semantic_density", "REAL"),
    ("passed_density_gate", "INTEGER"),
    ("passed_score_gate", "INTEGER"),
    ("passed_pacing_gate", "INTEGER"),
    ("spoken", "INTEGER"),
    ("discard_reason", "TEXT"),
    ("cooldown_remaining_at_eval", "REAL"),
    ("llm_latency_ms", "REAL"),
    ("tts_latency_ms", "REAL"),
)


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


def _table_column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def _create_events_table(conn: sqlite3.Connection) -> None:
    cols = ",\n            ".join(
        f"{name} {decl}" for name, decl in _EVENT_ANALYTICS_COLUMNS
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            payload_json TEXT NOT NULL,
            correlation_json TEXT,
            {cols}
        )
        """
    )


def _ensure_auxiliary_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_reactor_results (
            event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            comment TEXT NOT NULL,
            score REAL NOT NULL,
            comment_type TEXT NOT NULL,
            raw_response TEXT NOT NULL,
            PRIMARY KEY (event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS heckler_eval_labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            label_name TEXT NOT NULL,
            label_value TEXT,
            extra_json TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
        """
    )


def _ensure_analytics_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_events_utterance_timestamp
        ON events (utterance_id, timestamp_iso)
        """
    )


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Upgrade schema version 1 → 2: add columns, backfill from ``payload_json``, reactor child rows."""
    logger.info(
        "heckler event_store: migrating SQLite schema from version 1 to %s",
        SCHEMA_VERSION,
    )
    cols = _table_column_names(conn, "events")
    for name, decl in _EVENT_ANALYTICS_COLUMNS:
        if name not in cols:
            conn.execute(f"ALTER TABLE events ADD COLUMN {name} {decl}")

    # Backfill normalized event columns from legacy JSON (skip invalid JSON rows).
    conn.execute(
        """
        UPDATE events
        SET
            utterance_id = json_extract(payload_json, '$.utterance_id'),
            timestamp_iso = json_extract(payload_json, '$.timestamp_iso'),
            transcript = json_extract(payload_json, '$.transcript'),
            semantic_density = json_extract(payload_json, '$.semantic_density'),
            passed_density_gate = json_extract(payload_json, '$.passed_density_gate'),
            passed_score_gate = json_extract(payload_json, '$.passed_score_gate'),
            passed_pacing_gate = json_extract(payload_json, '$.passed_pacing_gate'),
            spoken = json_extract(payload_json, '$.spoken'),
            discard_reason = json_extract(payload_json, '$.discard_reason'),
            cooldown_remaining_at_eval = json_extract(
                payload_json, '$.cooldown_remaining_at_eval'
            ),
            llm_latency_ms = json_extract(payload_json, '$.llm_latency_ms'),
            tts_latency_ms = json_extract(payload_json, '$.tts_latency_ms')
        WHERE json_valid(payload_json)
        """
    )

    conn.execute(
        """
        INSERT INTO event_reactor_results (
            event_id, comment, score, comment_type, raw_response
        )
        SELECT
            e.id,
            json_extract(e.payload_json, '$.reactor_result.comment'),
            json_extract(e.payload_json, '$.reactor_result.score'),
            json_extract(e.payload_json, '$.reactor_result.comment_type'),
            json_extract(e.payload_json, '$.reactor_result.raw_response')
        FROM events e
        WHERE json_valid(e.payload_json)
          AND json_type(e.payload_json, '$.reactor_result') = 'object'
          AND json_extract(e.payload_json, '$.reactor_result.comment') IS NOT NULL
          AND json_extract(e.payload_json, '$.reactor_result.score') IS NOT NULL
          AND json_extract(e.payload_json, '$.reactor_result.comment_type') IS NOT NULL
          AND json_extract(e.payload_json, '$.reactor_result.raw_response') IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM event_reactor_results r WHERE r.event_id = e.id
          )
        """
    )

    conn.execute(
        "UPDATE heckler_schema_version SET version = ? WHERE id = 1",
        (SCHEMA_VERSION,),
    )


def init_schema(conn: sqlite3.Connection) -> None:
    """Create schema tables and record ``SCHEMA_VERSION``.

    Runs automatic upgrades from older supported versions (see ``.dev/decision-logs/T21-event-decomposition-schema.md``).

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
    _create_events_table(conn)
    _ensure_auxiliary_tables(conn)
    # Close the implicit DDL transaction so ``BEGIN IMMEDIATE`` in migrations can start cleanly.
    conn.commit()

    row = conn.execute(
        "SELECT version FROM heckler_schema_version WHERE id = 1"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO heckler_schema_version (id, version) VALUES (1, ?)",
            (SCHEMA_VERSION,),
        )
    else:
        stored = int(row[0])
        if stored > SCHEMA_VERSION:
            raise RuntimeError(
                f"unsupported heckler schema version {stored}, expected {SCHEMA_VERSION}"
            )
        while stored < SCHEMA_VERSION:
            if stored == 1:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    _migrate_v1_to_v2(conn)
                    conn.commit()
                except BaseException:
                    conn.rollback()
                    raise
                stored = SCHEMA_VERSION
            else:
                raise RuntimeError(
                    f"unsupported heckler schema version {stored}, expected {SCHEMA_VERSION}"
                )

    _ensure_analytics_indexes(conn)
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


def _heckle_event_analytics_params(event: HeckleEvent) -> tuple:
    """Bind tuple for ``_EVENT_ANALYTICS_COLUMNS`` order (SQLite affinities)."""
    dr = event.discard_reason.value if event.discard_reason is not None else None
    return (
        event.utterance_id,
        event.timestamp_iso,
        event.transcript,
        float(event.semantic_density),
        int(event.passed_density_gate),
        None if event.passed_score_gate is None else int(event.passed_score_gate),
        None if event.passed_pacing_gate is None else int(event.passed_pacing_gate),
        int(event.spoken),
        dr,
        event.cooldown_remaining_at_eval,
        event.llm_latency_ms,
        event.tts_latency_ms,
    )


def insert_heckle_event_row(
    conn: sqlite3.Connection,
    *,
    event: HeckleEvent,
    payload_json: str,
    correlation_json: str | None = None,
) -> int:
    """Insert one persisted event for the live logger: ``payload_json`` plus normalized columns.

    Writes the same ``payload_json`` string the caller built from
    :func:`~heckler.models.serialize_heckle_event` (round-trip / import contract). Populates
    analytics columns on ``events`` per schema v2. When ``event.reactor_result`` is set,
    inserts one row into ``event_reactor_results`` keyed by the new ``events.id``.

    The parent insert and optional child insert run in a **single SQLite transaction**
    (``commit`` on success, ``rollback`` on failure). Intended for the shared logger
    connection after :func:`init_schema`; do not interleave with other manual transactions
    on the same connection unless you rely on SQLite's single active transaction semantics.
    """
    col_names = ", ".join(name for name, _ in _EVENT_ANALYTICS_COLUMNS)
    placeholders = ", ".join("?" for _ in _EVENT_ANALYTICS_COLUMNS)
    sql_events = (
        f"INSERT INTO events (payload_json, correlation_json, {col_names}) "
        f"VALUES (?, ?, {placeholders})"
    )
    params_events = (payload_json, correlation_json) + _heckle_event_analytics_params(event)

    cur = conn.cursor()
    try:
        cur.execute(sql_events, params_events)
        event_id = int(cur.lastrowid)
        rr = event.reactor_result
        if rr is not None:
            cur.execute(
                """
                INSERT INTO event_reactor_results (
                    event_id, comment, score, comment_type, raw_response
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    rr.comment,
                    rr.score,
                    rr.comment_type.value,
                    rr.raw_response,
                ),
            )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        cur.close()
    return event_id
