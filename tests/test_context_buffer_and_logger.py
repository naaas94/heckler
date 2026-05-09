import json
import threading
from dataclasses import asdict
from datetime import date

import heckler.logger as logger_module

from heckler.config import HecklerConfig
from heckler.context_buffer import ContextBuffer
from heckler.logger import HecklerLogger
from heckler.models import (
    CommentType,
    DiscardReason,
    HeckleEvent,
    ReactorResult,
)


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


def test_logger_log_dir_created(tmp_path):
    cfg = HecklerConfig(log_dir=str(tmp_path / "logs"))
    HecklerLogger(cfg)
    assert (tmp_path / "logs").is_dir()


def test_logger_appends_jsonl_with_expected_path(tmp_path, monkeypatch):
    class FakeDate:
        @staticmethod
        def today():
            return date(2026, 3, 15)

    monkeypatch.setattr(logger_module, "date", FakeDate)

    cfg = HecklerConfig(log_dir=str(tmp_path / "logs"))
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

    log_file = tmp_path / "logs" / "heckler_2026-03-15.jsonl"
    assert log_file.is_file()
    line = log_file.read_text(encoding="utf-8").strip()
    row = json.loads(line)
    assert row["reactor_result"]["comment_type"] == "observation"
    assert row["discard_reason"] == "score_gate"
    assert "audio_chunk" not in line


def test_serialize_strips_top_level_audio_chunk(tmp_path, monkeypatch):
    cfg = HecklerConfig(log_dir=str(tmp_path / "logs"))
    logger = HecklerLogger(cfg)
    event = _minimal_event()
    fake = dict(asdict(event))
    fake["audio_chunk"] = {"x": 1}
    monkeypatch.setattr(logger_module.dataclasses, "asdict", lambda e: fake)
    text = logger._serialize(event)
    assert "audio_chunk" not in text


def test_logger_unicode_transcript_preserved(tmp_path, monkeypatch):
    class FakeDate:
        @staticmethod
        def today():
            return date(2026, 1, 1)

    monkeypatch.setattr(logger_module, "date", FakeDate)
    cfg = HecklerConfig(log_dir=str(tmp_path / "logs"))
    logger = HecklerLogger(cfg)
    event = _minimal_event(transcript="café 日本語")
    logger.log_event(event)
    line = (tmp_path / "logs" / "heckler_2026-01-01.jsonl").read_text(encoding="utf-8")
    row = json.loads(line)
    assert row["transcript"] == "café 日本語"


def test_concurrent_log_events_yield_one_json_object_per_line(tmp_path, monkeypatch):
    class FakeDate:
        @staticmethod
        def today():
            return date(2026, 6, 1)

    monkeypatch.setattr(logger_module, "date", FakeDate)
    cfg = HecklerConfig(log_dir=str(tmp_path / "logs"))
    logger = HecklerLogger(cfg)

    def worker(idx: int) -> None:
        logger.log_event(_minimal_event(utterance_id=f"id-{idx}", transcript=str(idx)))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    raw = (tmp_path / "logs" / "heckler_2026-06-01.jsonl").read_text(encoding="utf-8")
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    assert len(lines) == 20
    for ln in lines:
        json.loads(ln)


def test_log_path_changes_when_calendar_day_changes(tmp_path, monkeypatch):
    cfg = HecklerConfig(log_dir=str(tmp_path / "logs"))
    logger = HecklerLogger(cfg)
    event = _minimal_event()

    seq = iter([date(2026, 1, 1), date(2026, 1, 2)])

    class FakeDate:
        @staticmethod
        def today():
            return next(seq)

    monkeypatch.setattr(logger_module, "date", FakeDate)
    logger.log_event(event)
    logger.log_event(event)

    assert (tmp_path / "logs" / "heckler_2026-01-01.jsonl").is_file()
    assert (tmp_path / "logs" / "heckler_2026-01-02.jsonl").is_file()
