"""Tests for ``heckler/event_store`` and ``heckler/tracing_context``."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest

from heckler.event_store import (
    SCHEMA_VERSION,
    init_schema,
    insert_event_row,
    open_store,
)
from heckler.tracing_context import (
    clear_correlation,
    get_correlation,
    reset_correlation,
    set_correlation,
)


def test_open_store_creates_parent_and_init_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "db.sqlite"
    conn = open_store(db_path)
    try:
        init_schema(conn)
        row = conn.execute(
            "SELECT version FROM heckler_schema_version WHERE id = 1"
        ).fetchone()
        assert row is not None
        assert row[0] == SCHEMA_VERSION
        mode = conn.execute("PRAGMA journal_mode").fetchone()
        assert mode is not None and mode[0].lower() == "wal"
    finally:
        conn.close()


def test_insert_event_row_round_trip(tmp_path: Path) -> None:
    conn = open_store(tmp_path / "t.sqlite")
    try:
        init_schema(conn)
        payload = json.dumps({"utterance_id": "u1", "transcript": "hi"})
        rid = insert_event_row(conn, payload, '{"trace":"abc"}')
        assert rid >= 1
        row = conn.execute(
            "SELECT payload_json, correlation_json FROM events WHERE id = ?",
            (rid,),
        ).fetchone()
        assert row is not None
        assert json.loads(row[0])["utterance_id"] == "u1"
        assert json.loads(row[1])["trace"] == "abc"
    finally:
        conn.close()


def test_insert_event_row_with_cursor_commit(tmp_path: Path) -> None:
    conn = open_store(tmp_path / "c.sqlite")
    try:
        init_schema(conn)
        cur = conn.cursor()
        rid = insert_event_row(cur, "{}", None)
        conn.commit()
        row = conn.execute("SELECT id FROM events WHERE id = ?", (rid,)).fetchone()
        assert row is not None
    finally:
        conn.close()


def test_insert_without_schema_raises(tmp_path: Path) -> None:
    conn = open_store(tmp_path / "bare.sqlite")
    try:
        with pytest.raises(sqlite3.OperationalError):
            insert_event_row(conn, "{}", None)
    finally:
        conn.close()


def test_concurrent_inserts_with_shared_lock(tmp_path: Path) -> None:
    conn = open_store(tmp_path / "conc.sqlite")
    init_schema(conn)
    lock = threading.Lock()
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            for _ in range(20):
                with lock:
                    insert_event_row(conn, json.dumps({"i": i}), None)
        except BaseException as e:  # pragma: no cover - threads report failure
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    try:
        assert not errors
        (count,) = conn.execute("SELECT COUNT(*) FROM events").fetchone()
        assert count == 4 * 20
    finally:
        conn.close()


def test_schema_version_mismatch_raises(tmp_path: Path) -> None:
    conn = open_store(tmp_path / "ver.sqlite")
    try:
        conn.execute(
            """
            CREATE TABLE heckler_schema_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO heckler_schema_version (id, version) VALUES (1, 999)"
        )
        conn.execute(
            """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                payload_json TEXT NOT NULL,
                correlation_json TEXT
            )
            """
        )
        conn.commit()
        with pytest.raises(RuntimeError, match="unsupported heckler schema version"):
            init_schema(conn)
    finally:
        conn.close()


def test_tracing_context_set_get_clear() -> None:
    assert get_correlation() is None
    set_correlation({"response_id": "x", "provider": "openai"})
    assert get_correlation() == {"response_id": "x", "provider": "openai"}
    clear_correlation()
    assert get_correlation() is None


def test_tracing_context_none_clears() -> None:
    set_correlation({"a": "b"})
    set_correlation(None)
    assert get_correlation() is None


def test_tracing_context_thread_isolation() -> None:
    clear_correlation()
    ready = threading.Barrier(2)
    seen: dict[str, dict[str, str] | None] = {}

    def other_thread() -> None:
        ready.wait()
        seen["other"] = get_correlation()

    set_correlation({"main": "yes"})
    t = threading.Thread(target=other_thread)
    t.start()
    ready.wait()
    assert get_correlation() == {"main": "yes"}
    t.join()
    assert seen["other"] is None


def test_reset_correlation_alias() -> None:
    set_correlation({"k": "v"})
    reset_correlation()
    assert get_correlation() is None


# Adversarial gap addressed: concurrent threads mutating tracing **without** clearing —
# values remain unless explicitly cleared (documented reaction-worker lifecycle).
def test_tracing_context_overwrite_without_clear() -> None:
    set_correlation({"first": "1"})
    set_correlation({"second": "2"})
    assert get_correlation() == {"second": "2"}


def _write_v1_schema_db(path: Path) -> None:
    """Create an on-disk DB matching schema version 1 (pre-decomposition)."""
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE heckler_schema_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL
            );
            INSERT INTO heckler_schema_version (id, version) VALUES (1, 1);
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                payload_json TEXT NOT NULL,
                correlation_json TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_v1_on_disk_database_migrates_to_v2_and_backfills(tmp_path: Path) -> None:
    """Upgraded fixture: automatic v1→v2 migration per T20 Flag 2."""
    db_path = tmp_path / "legacy_v1.sqlite"
    _write_v1_schema_db(db_path)
    payload = {
        "utterance_id": "u-migrate",
        "timestamp_iso": "2026-05-11T12:00:00Z",
        "transcript": "hello",
        "semantic_density": 0.42,
        "passed_density_gate": True,
        "reactor_result": {
            "comment": "nice",
            "score": 0.9,
            "comment_type": "observation",
            "raw_response": '{"comment":"nice"}',
        },
        "passed_score_gate": True,
        "passed_pacing_gate": True,
        "spoken": False,
        "discard_reason": None,
        "cooldown_remaining_at_eval": None,
        "llm_latency_ms": 100.0,
        "tts_latency_ms": None,
    }
    raw_conn = sqlite3.connect(str(db_path))
    try:
        raw_conn.execute(
            "INSERT INTO events (payload_json, correlation_json) VALUES (?, ?)",
            (json.dumps(payload), '{"completion_id":"c1"}'),
        )
        raw_conn.commit()
    finally:
        raw_conn.close()

    conn = open_store(db_path)
    try:
        init_schema(conn)
        ver = conn.execute(
            "SELECT version FROM heckler_schema_version WHERE id = 1"
        ).fetchone()
        assert ver is not None and ver[0] == SCHEMA_VERSION
        cols = {r[1] for r in conn.execute("PRAGMA table_info(events)").fetchall()}
        assert "utterance_id" in cols and "semantic_density" in cols
        row = conn.execute(
            """
            SELECT utterance_id, transcript, json_extract(correlation_json, '$.completion_id')
            FROM events WHERE utterance_id = ?
            """,
            ("u-migrate",),
        ).fetchone()
        assert row is not None
        assert row[0] == "u-migrate"
        assert row[1] == "hello"
        assert row[2] == "c1"
        (rc,) = conn.execute(
            "SELECT COUNT(*) FROM event_reactor_results"
        ).fetchone()
        assert rc == 1
        rr = conn.execute(
            "SELECT comment, score, comment_type FROM event_reactor_results"
        ).fetchone()
        assert rr is not None
        assert rr[0] == "nice" and abs(rr[1] - 0.9) < 1e-9 and rr[2] == "observation"
    finally:
        conn.close()


def test_init_schema_idempotent_after_v1_migration(tmp_path: Path) -> None:
    """Second init on an already-migrated file must not duplicate reactor rows."""
    db_path = tmp_path / "idempotent.sqlite"
    _write_v1_schema_db(db_path)
    payload = {
        "utterance_id": "u1",
        "timestamp_iso": "2026-05-11T12:00:00Z",
        "transcript": "x",
        "semantic_density": 1.0,
        "passed_density_gate": True,
        "reactor_result": {
            "comment": "c",
            "score": 1.0,
            "comment_type": "sarcasm",
            "raw_response": "{}",
        },
        "passed_score_gate": True,
        "passed_pacing_gate": True,
        "spoken": True,
        "discard_reason": None,
        "cooldown_remaining_at_eval": None,
        "llm_latency_ms": None,
        "tts_latency_ms": None,
    }
    raw_conn = sqlite3.connect(str(db_path))
    try:
        raw_conn.execute(
            "INSERT INTO events (payload_json, correlation_json) VALUES (?, ?)",
            (json.dumps(payload), None),
        )
        raw_conn.commit()
    finally:
        raw_conn.close()

    conn = open_store(db_path)
    try:
        init_schema(conn)
        init_schema(conn)
        (rc,) = conn.execute(
            "SELECT COUNT(*) FROM event_reactor_results"
        ).fetchone()
        assert rc == 1
    finally:
        conn.close()


def test_v1_migration_skips_invalid_json_payload(tmp_path: Path) -> None:
    """Invalid ``payload_json`` must not abort migration; normalized columns stay NULL."""
    db_path = tmp_path / "bad_json.sqlite"
    _write_v1_schema_db(db_path)
    raw_conn = sqlite3.connect(str(db_path))
    try:
        raw_conn.execute(
            "INSERT INTO events (payload_json, correlation_json) VALUES (?, ?)",
            ("not-json", None),
        )
        raw_conn.commit()
    finally:
        raw_conn.close()

    conn = open_store(db_path)
    try:
        init_schema(conn)
        row = conn.execute(
            "SELECT utterance_id FROM events WHERE payload_json = ?",
            ("not-json",),
        ).fetchone()
        assert row is not None
        assert row[0] is None
    finally:
        conn.close()
