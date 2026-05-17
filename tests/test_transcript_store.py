"""Tests for ``heckler/transcript_store``."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from heckler.event_store import open_store
from heckler.transcript_store import (
    TRANSCRIPT_SCHEMA_VERSION,
    close_session,
    create_session,
    export_session_markdown,
    get_chunks,
    get_session,
    init_transcript_schema,
    insert_chunk,
)


def _memory_conn() -> sqlite3.Connection:
    return open_store(Path(":memory:"))


def test_init_transcript_schema_sets_version() -> None:
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        row = conn.execute(
            "SELECT version FROM transcript_schema_version WHERE id = 1"
        ).fetchone()
        assert row is not None
        assert int(row[0]) == TRANSCRIPT_SCHEMA_VERSION
    finally:
        conn.close()


def test_init_transcript_schema_idempotent() -> None:
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        init_transcript_schema(conn)
        row = conn.execute(
            "SELECT version FROM transcript_schema_version WHERE id = 1"
        ).fetchone()
        assert int(row[0]) == TRANSCRIPT_SCHEMA_VERSION
    finally:
        conn.close()


def test_init_transcript_schema_rejects_newer_version() -> None:
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        conn.execute(
            "UPDATE transcript_schema_version SET version = ? WHERE id = 1",
            (TRANSCRIPT_SCHEMA_VERSION + 10,),
        )
        conn.commit()
        with pytest.raises(RuntimeError, match="unsupported transcript schema"):
            init_transcript_schema(conn)
    finally:
        conn.close()


def test_create_session_insert_chunk_round_trip() -> None:
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        sid = "sess-a"
        created = create_session(conn, session_id=sid, name="Test")
        assert created.id == sid
        assert created.name == "Test"
        assert created.ended_at is None

        loaded = get_session(conn, sid)
        assert loaded is not None
        assert loaded.id == sid
        assert loaded.name == "Test"

        rid = insert_chunk(
            conn,
            session_id=sid,
            chunk_text="hello",
            timestamp_iso="2026-05-16T12:00:00+00:00",
            duration_s=1.5,
            sequence_num=0,
        )
        assert rid >= 1

        chunks = get_chunks(conn, sid)
        assert len(chunks) == 1
        assert chunks[0].id == rid
        assert chunks[0].chunk_text == "hello"
        assert chunks[0].sequence_num == 0
        assert chunks[0].duration_s == 1.5
    finally:
        conn.close()


def test_insert_chunk_unknown_session_raises() -> None:
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        with pytest.raises(sqlite3.IntegrityError):
            insert_chunk(
                conn,
                session_id="missing",
                chunk_text="x",
                timestamp_iso="2026-05-16T12:00:00+00:00",
                duration_s=None,
                sequence_num=0,
            )
    finally:
        conn.close()


def test_get_chunks_orders_by_sequence_then_id() -> None:
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        sid = "sess-order"
        create_session(conn, session_id=sid, name="n")
        r1 = insert_chunk(
            conn,
            session_id=sid,
            chunk_text="second",
            timestamp_iso="t2",
            duration_s=None,
            sequence_num=1,
        )
        r0 = insert_chunk(
            conn,
            session_id=sid,
            chunk_text="first",
            timestamp_iso="t1",
            duration_s=None,
            sequence_num=0,
        )
        r1b = insert_chunk(
            conn,
            session_id=sid,
            chunk_text="tie-break",
            timestamp_iso="t3",
            duration_s=None,
            sequence_num=1,
        )
        chunks = get_chunks(conn, sid)
        texts = [c.chunk_text for c in chunks]
        assert texts == ["first", "second", "tie-break"]
        ids = [c.id for c in chunks]
        assert ids == [r0, r1, r1b]
    finally:
        conn.close()


def test_close_session_sets_ended_at_and_second_close_noops() -> None:
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        sid = "sess-close"
        create_session(conn, session_id=sid, name="n")
        close_session(conn, sid)
        row = get_session(conn, sid)
        assert row is not None
        assert row.ended_at is not None
        ended_first = row.ended_at
        close_session(conn, sid)
        row2 = get_session(conn, sid)
        assert row2 is not None
        assert row2.ended_at == ended_first
    finally:
        conn.close()


def test_get_session_missing_returns_none() -> None:
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        assert get_session(conn, "nope") is None
    finally:
        conn.close()


def test_get_chunks_empty_session() -> None:
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        create_session(conn, session_id="empty", name="e")
        assert get_chunks(conn, "empty") == []
    finally:
        conn.close()


def test_export_session_markdown_format_multiple_chunks(tmp_path: Path) -> None:
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        sid = "sess-md"
        create_session(conn, session_id=sid, name="Interview")
        # started_at is set by create_session; align chunk times to +12s and +64s from it.
        loaded = get_session(conn, sid)
        assert loaded is not None
        base = loaded.started_at
        t0 = datetime.fromisoformat(base.replace("Z", "+00:00"))
        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=timezone.utc)
        t12 = (t0 + timedelta(seconds=12)).isoformat()
        t64 = (t0 + timedelta(seconds=64)).isoformat()

        insert_chunk(
            conn,
            session_id=sid,
            chunk_text="So tell me about your experience with...",
            timestamp_iso=t12,
            duration_s=None,
            sequence_num=0,
        )
        insert_chunk(
            conn,
            session_id=sid,
            chunk_text="I've been working in distributed systems for about five years now...",
            timestamp_iso=t64,
            duration_s=None,
            sequence_num=1,
        )

        out = tmp_path / "out.md"
        export_session_markdown(conn, sid, out)
        text = out.read_text(encoding="utf-8")
        date_part = t0.date().isoformat()
        assert text.startswith(f"# Interview — {date_part}")
        assert "[00:00:12] So tell me about your experience with..." in text
        assert "[00:01:04] I've been working in distributed systems" in text
        # blank line between chunk blocks
        assert "\n\n[00:01:04]" in text
    finally:
        conn.close()


def test_export_session_markdown_empty_session_header_only(tmp_path: Path) -> None:
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        sid = "sess-empty-md"
        create_session(conn, session_id=sid, name="Solo")
        loaded = get_session(conn, sid)
        assert loaded is not None
        started = datetime.fromisoformat(loaded.started_at.replace("Z", "+00:00"))
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        date_part = started.date().isoformat()
        out = tmp_path / "e.md"
        export_session_markdown(conn, sid, out)
        text = out.read_text(encoding="utf-8")
        assert text.strip() == f"# Solo — {date_part}"
    finally:
        conn.close()


def test_export_session_markdown_creates_parent_directories(tmp_path: Path) -> None:
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        sid = "sess-nested"
        create_session(conn, session_id=sid, name="n")
        insert_chunk(
            conn,
            session_id=sid,
            chunk_text="only",
            timestamp_iso="2026-05-16T00:00:05+00:00",
            duration_s=None,
            sequence_num=0,
        )
        out = tmp_path / "a" / "b" / "c.md"
        export_session_markdown(conn, sid, out)
        assert out.is_file()
        assert "only" in out.read_text(encoding="utf-8")
    finally:
        conn.close()


def test_export_session_markdown_missing_session_raises(tmp_path: Path) -> None:
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        with pytest.raises(RuntimeError, match="transcript session not found"):
            export_session_markdown(conn, "no-such-session", tmp_path / "x.md")
    finally:
        conn.close()


def test_export_session_markdown_invalid_chunk_timestamp_raises(
    tmp_path: Path,
) -> None:
    """Malformed ``timestamp_iso`` is a caller/DB contract violation; export surfaces it."""
    conn = _memory_conn()
    try:
        init_transcript_schema(conn)
        sid = "sess-bad-ts"
        create_session(conn, session_id=sid, name="x")
        insert_chunk(
            conn,
            session_id=sid,
            chunk_text="hi",
            timestamp_iso="not-an-iso-timestamp",
            duration_s=None,
            sequence_num=0,
        )
        with pytest.raises(ValueError):
            export_session_markdown(conn, sid, tmp_path / "bad.md")
    finally:
        conn.close()
