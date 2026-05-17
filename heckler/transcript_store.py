"""SQLite persistence for transcribe-mode transcript sessions and chunks (stdlib ``sqlite3`` only).

Call :func:`~heckler.event_store.open_store` for a configured connection, then
:func:`init_transcript_schema` once per database file. Transcript tables live alongside
heckler event tables in the same file when configured that way, but use a separate
schema version row in ``transcript_schema_version`` (not ``heckler_schema_version``).
"""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

TRANSCRIPT_SCHEMA_VERSION: int = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_timestamp(value: str) -> datetime:
    """Parse ISO-8601 timestamps from the DB (UTC ``Z`` normalized to an offset)."""
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _format_hhmmss(total_seconds: float) -> str:
    if total_seconds < 0:
        total_seconds = 0.0
    whole = int(total_seconds)
    h, rem = divmod(whole, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


@dataclass
class TranscriptSession:
    id: str
    name: str
    started_at: str
    ended_at: Optional[str]


@dataclass
class TranscriptChunk:
    id: Optional[int]
    session_id: str
    chunk_text: str
    timestamp_iso: str
    duration_s: Optional[float]
    sequence_num: int


def init_transcript_schema(conn: sqlite3.Connection) -> None:
    """Create transcript tables and record ``TRANSCRIPT_SCHEMA_VERSION``.

    Raises ``RuntimeError`` if an existing database reports an unsupported transcript
    schema version (same policy shape as :func:`~heckler.event_store.init_schema`).
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transcript_schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transcript_sessions (
            id TEXT PRIMARY KEY,
            name TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transcript_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES transcript_sessions(id),
            chunk_text TEXT NOT NULL,
            timestamp_iso TEXT NOT NULL,
            duration_s REAL,
            sequence_num INTEGER
        )
        """
    )
    conn.commit()

    row = conn.execute(
        "SELECT version FROM transcript_schema_version WHERE id = 1"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO transcript_schema_version (id, version) VALUES (1, ?)",
            (TRANSCRIPT_SCHEMA_VERSION,),
        )
        conn.commit()
    else:
        stored = int(row[0])
        if stored > TRANSCRIPT_SCHEMA_VERSION:
            raise RuntimeError(
                f"unsupported transcript schema version {stored}, "
                f"expected {TRANSCRIPT_SCHEMA_VERSION}"
            )
        if stored < TRANSCRIPT_SCHEMA_VERSION:
            raise RuntimeError(
                f"unsupported transcript schema version {stored}, "
                f"expected {TRANSCRIPT_SCHEMA_VERSION}"
            )


def create_session(
    conn: sqlite3.Connection, *, session_id: str, name: str
) -> TranscriptSession:
    """Insert a new transcript session row and return the persisted record."""
    started_at = _utc_now_iso()
    try:
        conn.execute(
            """
            INSERT INTO transcript_sessions (id, name, started_at, ended_at)
            VALUES (?, ?, ?, NULL)
            """,
            (session_id, name, started_at),
        )
        conn.commit()
    except sqlite3.Error:
        logger.error(
            "transcript_store: failed to create session",
            extra={"session_id": session_id},
        )
        raise
    logger.info(
        "transcript_store: session started",
        extra={"session_id": session_id},
    )
    return TranscriptSession(
        id=session_id, name=name, started_at=started_at, ended_at=None
    )


def close_session(conn: sqlite3.Connection, session_id: str) -> None:
    """Set ``ended_at`` for the session if it exists."""
    ended_at = _utc_now_iso()
    try:
        cur = conn.execute(
            """
            UPDATE transcript_sessions
            SET ended_at = ?
            WHERE id = ? AND ended_at IS NULL
            """,
            (ended_at, session_id),
        )
        conn.commit()
        if cur.rowcount:
            logger.info(
                "transcript_store: session stopped",
                extra={"session_id": session_id},
            )
    except sqlite3.Error:
        logger.error(
            "transcript_store: failed to close session",
            extra={"session_id": session_id},
        )
        raise


def insert_chunk(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    chunk_text: str,
    timestamp_iso: str,
    duration_s: Optional[float],
    sequence_num: int,
) -> int:
    """Insert one chunk row; returns SQLite ``rowid`` for ``transcript_chunks``."""
    try:
        cur = conn.execute(
            """
            INSERT INTO transcript_chunks (
                session_id, chunk_text, timestamp_iso, duration_s, sequence_num
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, chunk_text, timestamp_iso, duration_s, sequence_num),
        )
        rowid = int(cur.lastrowid)
        conn.commit()
    except sqlite3.Error:
        logger.error(
            "transcript_store: failed to insert chunk",
            extra={"session_id": session_id, "chunk_sequence_num": sequence_num},
        )
        raise
    logger.info(
        "transcript_store: chunk persisted",
        extra={"session_id": session_id, "chunk_sequence_num": sequence_num},
    )
    return rowid


def get_session(conn: sqlite3.Connection, session_id: str) -> Optional[TranscriptSession]:
    """Return the session row, or ``None`` if missing."""
    row = conn.execute(
        """
        SELECT id, name, started_at, ended_at
        FROM transcript_sessions
        WHERE id = ?
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return TranscriptSession(
        id=str(row[0]),
        name=str(row[1]),
        started_at=str(row[2]),
        ended_at=None if row[3] is None else str(row[3]),
    )


def get_chunks(conn: sqlite3.Connection, session_id: str) -> list[TranscriptChunk]:
    """Return all chunks for ``session_id`` ordered by ``sequence_num``, then ``id``."""
    rows = conn.execute(
        """
        SELECT id, session_id, chunk_text, timestamp_iso, duration_s, sequence_num
        FROM transcript_chunks
        WHERE session_id = ?
        ORDER BY sequence_num ASC, id ASC
        """,
        (session_id,),
    ).fetchall()
    out: list[TranscriptChunk] = []
    for r in rows:
        seq = r[5]
        out.append(
            TranscriptChunk(
                id=int(r[0]),
                session_id=str(r[1]),
                chunk_text=str(r[2]),
                timestamp_iso=str(r[3]),
                duration_s=None if r[4] is None else float(r[4]),
                sequence_num=int(seq) if seq is not None else 0,
            )
        )
    return out


def export_session_markdown(
    conn: sqlite3.Connection, session_id: str, output_path: Path
) -> None:
    """Write the full transcript for ``session_id`` to ``output_path`` (atomic replace).

    Reads current rows via :func:`get_session` / :func:`get_chunks` so callers may invoke
    this repeatedly during an open session; each call overwrites the file with the
    latest snapshot.
    """
    session = get_session(conn, session_id)
    if session is None:
        raise RuntimeError(f"transcript session not found: {session_id}")
    chunks = get_chunks(conn, session_id)

    started = _parse_iso_timestamp(session.started_at)
    heading_date = started.date().isoformat()
    lines: list[str] = [f"# {session.name} — {heading_date}", ""]

    for i, chunk in enumerate(chunks):
        chunk_started = _parse_iso_timestamp(chunk.timestamp_iso)
        rel_s = (chunk_started - started).total_seconds()
        stamp = _format_hhmmss(rel_s)
        lines.append(f"[{stamp}] {chunk.chunk_text}")
        if i < len(chunks) - 1:
            lines.append("")

    content = "\n".join(lines)
    if content and not content.endswith("\n"):
        content += "\n"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path: Optional[str] = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(output_path.parent),
            prefix=".transcript_export_",
            suffix=".tmp",
        )
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp_path, output_path)
        tmp_path = None
        logger.info(
            "transcript_store: session exported to markdown",
            extra={"session_id": session_id},
        )
    except OSError:
        logger.error(
            "transcript_store: markdown export failed",
            extra={"session_id": session_id},
        )
        raise
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
