import json
import logging
import sqlite3
import threading

import pytest

import heckler.logger as logger_module

from heckler.config import HecklerConfig
from heckler.context_buffer import ContextBuffer
from heckler.logger import HecklerLogger
from heckler.models import (
    CommentType,
    DiscardReason,
    HeckleEvent,
    ReactorResult,
    serialize_heckle_event,
)
from heckler.tracing_context import get_correlation, set_correlation


def _minimal_event(**kwargs) -> HeckleEvent:
    base = dict(
        utterance_id="u1",
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


def test_context_buffer_empty_block():
    buf = ContextBuffer(maxlen=3)
    assert buf.get_context_block() == ""


def test_context_buffer_numbered_block_and_order():
    buf = ContextBuffer(maxlen=10)
    buf.push("first")
    buf.push("second")
    assert buf.get_context_block() == "[1] first\n[2] second"


def test_context_buffer_respects_maxlen():
    buf = ContextBuffer(maxlen=2)
    buf.push("a")
    buf.push("b")
    buf.push("c")
    assert buf.get_context_block() == "[1] b\n[2] c"


def test_logger_creates_parent_directory_for_sqlite_path(tmp_path):
    cfg = HecklerConfig(sqlite_database_path=str(tmp_path / "logs" / "heckler.db"))
    HecklerLogger(cfg)
    assert (tmp_path / "logs").is_dir()


def test_logger_persists_event_row(tmp_path):
    cfg = HecklerConfig(sqlite_database_path=str(tmp_path / "logs" / "heckler.db"))
    logger = HecklerLogger(cfg)
    event = _minimal_event(
        reactor_result=ReactorResult(
            comment="x",
            score=0.9,
            comment_type=CommentType.OBSERVATION,
            raw_response="{}",
        ),
        passed_score_gate=True,
        passed_pacing_gate=True,
        discard_reason=DiscardReason.SCORE_GATE,
    )
    logger.log_event(event)

    db_file = tmp_path / "logs" / "heckler.db"
    conn = sqlite3.connect(str(db_file))
    try:
        row = conn.execute(
            "SELECT payload_json, correlation_json FROM events ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    payload = json.loads(row[0])
    assert payload["reactor_result"]["comment_type"] == "observation"
    assert payload["discard_reason"] == "score_gate"
    assert "audio_chunk" not in json.dumps(payload)
    assert row[1] is None


def test_logger_payload_matches_serialize_heckle_event(tmp_path):
    cfg = HecklerConfig(sqlite_database_path=str(tmp_path / "db.sqlite"))
    logger = HecklerLogger(cfg)
    event = _minimal_event(transcript="probe")
    logger.log_event(event)
    conn = sqlite3.connect(str(tmp_path / "db.sqlite"))
    try:
        (payload_raw,) = conn.execute(
            "SELECT payload_json FROM events ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert json.loads(payload_raw) == serialize_heckle_event(event)


def test_logger_unicode_transcript_preserved(tmp_path):
    cfg = HecklerConfig(sqlite_database_path=str(tmp_path / "logs" / "heckler.db"))
    logger = HecklerLogger(cfg)
    event = _minimal_event(transcript="café 日本語")
    logger.log_event(event)
    conn = sqlite3.connect(str(tmp_path / "logs" / "heckler.db"))
    try:
        (payload_raw,) = conn.execute(
            "SELECT payload_json FROM events ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert json.loads(payload_raw)["transcript"] == "café 日本語"


def test_concurrent_log_events_insert_distinct_rows(tmp_path):
    cfg = HecklerConfig(sqlite_database_path=str(tmp_path / "logs" / "heckler.db"))
    logger = HecklerLogger(cfg)

    def worker(idx: int) -> None:
        logger.log_event(_minimal_event(utterance_id=f"id-{idx}", transcript=str(idx)))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    conn = sqlite3.connect(str(tmp_path / "logs" / "heckler.db"))
    try:
        (count,) = conn.execute("SELECT COUNT(*) FROM events").fetchone()
    finally:
        conn.close()
    assert count == 20


def test_logger_writes_correlation_json_when_set(tmp_path):
    cfg = HecklerConfig(sqlite_database_path=str(tmp_path / "db.sqlite"))
    logger = HecklerLogger(cfg)
    set_correlation({"response_id": "rid-1", "provider": "mock"})
    event = _minimal_event()
    logger.log_event(event)
    assert get_correlation() is None

    conn = sqlite3.connect(str(tmp_path / "db.sqlite"))
    try:
        (corr_raw,) = conn.execute(
            "SELECT correlation_json FROM events ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert json.loads(corr_raw)["response_id"] == "rid-1"


def test_logger_insert_failure_logs_error_and_raises(tmp_path, monkeypatch, caplog):
    cfg = HecklerConfig(sqlite_database_path=str(tmp_path / "db.sqlite"))
    logger = HecklerLogger(cfg)

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(logger_module, "insert_event_row", boom)
    caplog.set_level(logging.ERROR)
    with pytest.raises(sqlite3.OperationalError, match="disk I/O error"):
        logger.log_event(_minimal_event())
    assert "SQLite event insert failed" in caplog.text


def test_logger_clears_correlation_after_failed_insert(tmp_path, monkeypatch):
    cfg = HecklerConfig(sqlite_database_path=str(tmp_path / "db.sqlite"))
    logger = HecklerLogger(cfg)
    set_correlation({"keep": "clean"})

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("fail")

    monkeypatch.setattr(logger_module, "insert_event_row", boom)
    with pytest.raises(sqlite3.OperationalError):
        logger.log_event(_minimal_event())
    assert get_correlation() is None


# Adversarial gap addressed: ``log_event`` uses ``serialize_heckle_event`` only — if a
# duplicate coercion path were reintroduced on the logger, this equality check would drift.
def test_logger_row_payload_equals_models_projection(tmp_path, monkeypatch):
    cfg = HecklerConfig(sqlite_database_path=str(tmp_path / "db.sqlite"))
    logger = HecklerLogger(cfg)
    event = _minimal_event()
    calls: list[HeckleEvent] = []

    def capture_serialize(e: HeckleEvent):
        calls.append(e)
        return serialize_heckle_event(e)

    monkeypatch.setattr(logger_module, "serialize_heckle_event", capture_serialize)
    logger.log_event(event)
    assert len(calls) == 1 and calls[0] is event
