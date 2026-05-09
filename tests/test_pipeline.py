import logging
import queue
import threading as _threading
from unittest.mock import MagicMock

import numpy as np

from heckler.config import HecklerConfig
from heckler.models import AudioChunk, CommentType, DiscardReason, ReactorResult, Utterance
from heckler.pacing_gate import PacingGate
from heckler.pipeline import (
    _execute_spoken_reply,
    _put_shutdown_sentinel,
    _run_reaction_worker,
    main,
)


def _audio_utt(transcript: str) -> Utterance:
    chunk = AudioChunk(audio=np.zeros(8, dtype=np.float32), captured_at=0.0)
    return Utterance(
        utterance_id="id-1",
        transcript=transcript,
        semantic_density=0.5,
        transcribed_at=1.0,
        audio_chunk=chunk,
    )


def test_main_shutdown_stops_capture_and_joins_threads(monkeypatch):
    cfg = HecklerConfig(anthropic_api_key="test-key")
    monkeypatch.setattr("heckler.pipeline.load_config", lambda: cfg)
    monkeypatch.setattr("heckler.pipeline.HecklerLogger", lambda _: MagicMock())

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe.return_value = ""
    monkeypatch.setattr("heckler.pipeline.Transcriber", lambda _: mock_transcriber)

    mock_speaker = MagicMock()
    mock_speaker.is_playing = _threading.Event()
    monkeypatch.setattr("heckler.pipeline.Speaker", lambda _: mock_speaker)
    monkeypatch.setattr("heckler.pipeline.Reactor", lambda _: MagicMock())

    mock_capture = MagicMock()
    monkeypatch.setattr(
        "heckler.pipeline.AudioCapture", lambda *a, **kw: mock_capture
    )

    monkeypatch.setattr(
        "heckler.pipeline.time.sleep",
        lambda _: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    spawned: list[_threading.Thread] = []
    _OrigThread = _threading.Thread

    class _TrackingThread(_OrigThread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            spawned.append(self)

    monkeypatch.setattr("heckler.pipeline.threading.Thread", _TrackingThread)

    main([])

    mock_capture.stop.assert_called_once()
    assert len(spawned) == 2
    for t in spawned:
        assert not t.is_alive(), f"Thread {t.name} still alive after main() returned"


def test_reaction_worker_falls_back_to_llm_error_when_react_returns_none_triple(
    caplog,
):
    """If ``react`` returns (None, latency, None), worker must not assert; log and use LLM_ERROR."""
    reaction_queue: queue.Queue = queue.Queue()
    reaction_queue.put(_audio_utt("bad-contract"))
    reaction_queue.put(None)

    reactor = MagicMock()
    reactor.react.return_value = (None, 99.0, None)

    heckler_logger = MagicMock()
    context_buffer = MagicMock()
    context_buffer.get_context_block.return_value = ""

    caplog.set_level(logging.ERROR, logger="heckler.pipeline")

    _run_reaction_worker(
        context_buffer=context_buffer,
        reactor=reactor,
        pacing_gate=MagicMock(),
        speaker=MagicMock(),
        heckler_logger=heckler_logger,
        reaction_queue=reaction_queue,
    )

    event = heckler_logger.log_event.call_args[0][0]
    assert event.discard_reason == DiscardReason.LLM_ERROR
    assert event.passed_score_gate is None
    assert "contract violation" in caplog.text


def test_list_devices_short_circuits(monkeypatch):
    called = {"load": 0}

    def boom():
        called["load"] += 1
        raise AssertionError("load_config must not run for --list-devices")

    monkeypatch.setattr("heckler.pipeline.load_config", boom)
    monkeypatch.setattr(
        "heckler.pipeline.sd.query_devices",
        lambda: [{"name": "dummy", "max_input_channels": 2}],
    )
    main(["--list-devices"])
    assert called["load"] == 0


def test_execute_spoken_reply_records_before_speak():
    order: list[str] = []
    cfg = HecklerConfig()
    pg = PacingGate(cfg)

    def record():
        order.append("record")

    def speak(_: str) -> float:
        order.append("speak")
        return 42.0

    pg.record_output = record  # type: ignore[method-assign]
    sp = MagicMock()
    sp.speak = speak  # type: ignore[method-assign]
    assert _execute_spoken_reply(pg, sp, "hi") == 42.0  # type: ignore[arg-type]
    assert order == ["record", "speak"]


def test_put_shutdown_sentinel_drops_oldest_when_queue_full():
    q: queue.Queue = queue.Queue(maxsize=2)
    q.put_nowait("drop-me")
    q.put_nowait("keep")
    _put_shutdown_sentinel(q)
    assert q.get_nowait() == "keep"
    assert q.get_nowait() is None


def test_reaction_worker_calls_reactor_react_directly():
    """Discard reasons come from ``reactor.react`` third element — no client monkey-patch."""
    reaction_queue: queue.Queue = queue.Queue()
    reaction_queue.put(_audio_utt("hello"))
    reaction_queue.put(None)

    reactor = MagicMock()
    reactor.react.return_value = (None, 12.5, DiscardReason.LLM_ERROR)

    heckler_logger = MagicMock()
    context_buffer = MagicMock()
    context_buffer.get_context_block.return_value = "ctx-block"

    _run_reaction_worker(
        context_buffer=context_buffer,
        reactor=reactor,
        pacing_gate=MagicMock(),
        speaker=MagicMock(),
        heckler_logger=heckler_logger,
        reaction_queue=reaction_queue,
    )

    reactor.react.assert_called_once()
    args, _kwargs = reactor.react.call_args
    assert args[0].transcript == "hello"
    assert args[1] == "ctx-block"
    heckler_logger.log_event.assert_called_once()
    event = heckler_logger.log_event.call_args[0][0]
    assert event.discard_reason == DiscardReason.LLM_ERROR
    assert event.passed_score_gate is None


def test_reaction_worker_maps_score_gate_discard_reason():
    reaction_queue: queue.Queue = queue.Queue()
    reaction_queue.put(_audio_utt("speech"))
    reaction_queue.put(None)

    reactor = MagicMock()
    reactor.react.return_value = (None, 3.0, DiscardReason.SCORE_GATE)

    heckler_logger = MagicMock()
    context_buffer = MagicMock()
    context_buffer.get_context_block.return_value = ""

    _run_reaction_worker(
        context_buffer=context_buffer,
        reactor=reactor,
        pacing_gate=MagicMock(),
        speaker=MagicMock(),
        heckler_logger=heckler_logger,
        reaction_queue=reaction_queue,
    )

    event = heckler_logger.log_event.call_args[0][0]
    assert event.discard_reason == DiscardReason.SCORE_GATE
    assert event.passed_score_gate is False


def test_reaction_worker_success_path_without_wrapper():
    reaction_queue: queue.Queue = queue.Queue()
    utt = _audio_utt("line")
    reaction_queue.put(utt)
    reaction_queue.put(None)

    rr = ReactorResult(
        comment="Neat.",
        score=0.9,
        comment_type=CommentType.OBSERVATION,
        raw_response="{}",
    )
    reactor = MagicMock()
    reactor.react.return_value = (rr, 8.0, None)

    pacing_gate = MagicMock()
    pacing_gate.evaluate.return_value = (True, 0.0)

    speaker = MagicMock()
    speaker.speak.return_value = 33.0

    heckler_logger = MagicMock()
    context_buffer = MagicMock()
    context_buffer.get_context_block.return_value = "ctx"

    _run_reaction_worker(
        context_buffer=context_buffer,
        reactor=reactor,
        pacing_gate=pacing_gate,
        speaker=speaker,
        heckler_logger=heckler_logger,
        reaction_queue=reaction_queue,
    )

    reactor.react.assert_called_once_with(utt, "ctx")
    speaker.speak.assert_called_once_with("Neat.")
    logged = [c.args[0] for c in heckler_logger.log_event.call_args_list]
    assert len(logged) == 1
    assert logged[0].spoken is True
    assert logged[0].discard_reason is None


def test_reaction_worker_pacing_gate_after_successful_react():
    """If ``react`` succeeds but pacing rejects, event must record ``PACING_GATE``."""
    reaction_queue: queue.Queue = queue.Queue()
    utt = _audio_utt("line")
    reaction_queue.put(utt)
    reaction_queue.put(None)

    rr = ReactorResult(
        comment="Late joke.",
        score=0.95,
        comment_type=CommentType.SARCASM,
        raw_response="{}",
    )
    reactor = MagicMock()
    reactor.react.return_value = (rr, 7.0, None)

    pacing_gate = MagicMock()
    pacing_gate.evaluate.return_value = (False, 2.5)

    heckler_logger = MagicMock()
    context_buffer = MagicMock()
    context_buffer.get_context_block.return_value = ""

    _run_reaction_worker(
        context_buffer=context_buffer,
        reactor=reactor,
        pacing_gate=pacing_gate,
        speaker=MagicMock(),
        heckler_logger=heckler_logger,
        reaction_queue=reaction_queue,
    )

    pacing_gate.evaluate.assert_called_once_with(0.95)
    event = heckler_logger.log_event.call_args[0][0]
    assert event.discard_reason == DiscardReason.PACING_GATE
    assert event.passed_pacing_gate is False
