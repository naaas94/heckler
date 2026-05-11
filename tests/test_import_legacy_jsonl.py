"""Tests for ``scripts/import_legacy_jsonl.py`` (T4 / T20 Flag 5)."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from heckler.event_store import init_schema, insert_event_row, insert_heckle_event_row, open_store
from heckler.models import (
    CommentType,
    HeckleEvent,
    ReactorResult,
    serialize_heckle_event,
)


def _load_import_script():
    root = Path(__file__).resolve().parent.parent
    path = root / "scripts" / "import_legacy_jsonl.py"
    spec = importlib.util.spec_from_file_location("import_legacy_jsonl_under_test", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _minimal_event(**kwargs) -> HeckleEvent:
    base = dict(
        utterance_id="u-import-1",
        timestamp_iso="2026-05-08T12:00:00+00:00",
        transcript="hello",
        semantic_density=0.5,
        passed_density_gate=True,
        reactor_result=None,
        passed_score_gate=None,
        passed_pacing_gate=None,
        spoken=False,
        discard_reason=None,
        cooldown_remaining_at_eval=None,
        llm_latency_ms=None,
        tts_latency_ms=None,
    )
    base.update(kwargs)
    return HeckleEvent(**base)


def _jsonl_line(event: HeckleEvent) -> str:
    return json.dumps(serialize_heckle_event(event), ensure_ascii=False)


@pytest.fixture
def import_mod():
    return _load_import_script()


def test_import_populates_normalized_columns_and_reactor_child(tmp_path, import_mod) -> None:
    event = _minimal_event(
        utterance_id="utt-norm",
        reactor_result=ReactorResult(
            comment="c1",
            score=0.8,
            comment_type=CommentType.SARCASM,
            raw_response="{}",
        ),
        passed_score_gate=True,
    )
    db = tmp_path / "db.sqlite"
    conn = open_store(db)
    try:
        init_schema(conn)
        import_mod.import_lines(
            conn,
            [_jsonl_line(event)],
            dry_run=False,
            skip_existing=False,
        )
        row = conn.execute(
            "SELECT utterance_id, transcript FROM events WHERE id = 1"
        ).fetchone()
        assert row is not None
        assert row[0] == "utt-norm" and row[1] == "hello"
        rr = conn.execute(
            "SELECT comment, score FROM event_reactor_results WHERE event_id = 1"
        ).fetchone()
        assert rr == ("c1", 0.8)
    finally:
        conn.close()


def test_skip_existing_detects_json_only_payload_row(tmp_path, import_mod) -> None:
    event = _minimal_event(utterance_id="utt-json-only")
    line = _jsonl_line(event)
    db = tmp_path / "db.sqlite"
    conn = open_store(db)
    try:
        init_schema(conn)
        payload = json.dumps(serialize_heckle_event(event), ensure_ascii=False)
        insert_event_row(conn, payload, None)
        ins, sd, sb, err = import_mod.import_lines(
            conn,
            [line],
            dry_run=False,
            skip_existing=True,
        )
        assert (ins, sd, sb, err) == (0, 1, 0, 0)
        (n,) = conn.execute("SELECT COUNT(*) FROM events").fetchone()
        assert n == 1
    finally:
        conn.close()


def test_skip_existing_matches_normalized_columns_without_json_keys(tmp_path, import_mod) -> None:
    """Falsifier: dedupe must not require json_extract hits when v2 columns already hold the pair."""
    event = _minimal_event(utterance_id="pre-col", timestamp_iso="2026-01-02T00:00:00Z")
    line = _jsonl_line(event)
    db = tmp_path / "db.sqlite"
    conn = open_store(db)
    try:
        init_schema(conn)
        conn.execute(
            """
            INSERT INTO events (payload_json, correlation_json, utterance_id, timestamp_iso)
            VALUES ('{}', NULL, 'pre-col', '2026-01-02T00:00:00Z')
            """
        )
        conn.commit()
        ins, sd, sb, err = import_mod.import_lines(
            conn,
            [line],
            dry_run=False,
            skip_existing=True,
        )
        assert (ins, sd, sb, err) == (0, 1, 0, 0)
        (n,) = conn.execute("SELECT COUNT(*) FROM events").fetchone()
        assert n == 1
    finally:
        conn.close()


def test_skip_existing_after_insert_heckle_event_row(tmp_path, import_mod) -> None:
    event = _minimal_event(utterance_id="live-logger-shape")
    line = _jsonl_line(event)
    db = tmp_path / "db.sqlite"
    conn = open_store(db)
    try:
        init_schema(conn)
        payload = json.dumps(serialize_heckle_event(event), ensure_ascii=False)
        insert_heckle_event_row(conn, event=event, payload_json=payload, correlation_json=None)
        ins, sd, sb, err = import_mod.import_lines(
            conn,
            [line],
            dry_run=False,
            skip_existing=True,
        )
        assert (ins, sd, sb, err) == (0, 1, 0, 0)
        (n,) = conn.execute("SELECT COUNT(*) FROM events").fetchone()
        assert n == 1
    finally:
        conn.close()


def test_two_distinct_lines_insert_two_normalized_rows(tmp_path, import_mod) -> None:
    db = tmp_path / "db.sqlite"
    conn = open_store(db)
    try:
        init_schema(conn)
        e1 = _minimal_event(utterance_id="a1")
        e2 = _minimal_event(utterance_id="a2", transcript="two")
        import_mod.import_lines(
            conn,
            [_jsonl_line(e1), _jsonl_line(e2)],
            dry_run=False,
            skip_existing=False,
        )
        rows = conn.execute(
            "SELECT utterance_id FROM events ORDER BY id"
        ).fetchall()
        assert [r[0] for r in rows] == ["a1", "a2"]
    finally:
        conn.close()
