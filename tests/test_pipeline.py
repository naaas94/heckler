import logging
import queue
import sqlite3
import threading as _threading
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from heckler.config import HecklerConfig
from heckler.models import AudioChunk, CommentType, DiscardReason, ReactorResult, Utterance
from heckler.pacing_gate import PacingGate
from heckler.persona import Persona, PersonaNotFoundError
from heckler.pipeline import (
    _execute_spoken_reply,
    _put_shutdown_sentinel,
    _run_reaction_worker,
    _run_transcribe_worker,
    main,
)
from heckler.transcript_store import create_session, init_transcript_schema


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
    fake_persona = Persona(
        name="heckler",
        description="",
        system_prompt="sys-prompt",
        examples=[],
        config_overrides={},
    )
    monkeypatch.setattr("heckler.pipeline.load_config", lambda: cfg)
    monkeypatch.setattr("heckler.pipeline.load_persona", lambda _path: fake_persona)
    monkeypatch.setattr(
        "heckler.pipeline.apply_persona_overrides", lambda base, _persona: base
    )
    monkeypatch.setattr("heckler.pipeline.HecklerLogger", lambda _: MagicMock())

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe.return_value = ""
    monkeypatch.setattr("heckler.pipeline.Transcriber", lambda _: mock_transcriber)

    mock_speaker = MagicMock()
    mock_speaker.is_playing = _threading.Event()
    monkeypatch.setattr("heckler.pipeline.Speaker", lambda _: mock_speaker)
    monkeypatch.setattr("heckler.pipeline.Reactor", lambda *a, **kw: MagicMock())

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


def test_main_persona_flag_overrides_config(monkeypatch):
    """``--persona`` CLI flag overrides ``config.persona_name`` for ``load_persona`` path."""
    cfg = HecklerConfig(anthropic_api_key="test-key", persona_name="heckler")
    seen: list[Path] = []

    def capture_load(persona_dir: Path) -> Persona:
        seen.append(persona_dir)
        return Persona(
            name="custom",
            description="",
            system_prompt="s",
            examples=[],
            config_overrides={},
        )

    monkeypatch.setattr("heckler.pipeline.load_config", lambda: cfg)
    monkeypatch.setattr("heckler.pipeline.load_persona", capture_load)
    monkeypatch.setattr(
        "heckler.pipeline.apply_persona_overrides", lambda base, _p: base
    )
    monkeypatch.setattr("heckler.pipeline.HecklerLogger", lambda _: MagicMock())
    monkeypatch.setattr("heckler.pipeline.Transcriber", lambda _: MagicMock())
    mock_speaker = MagicMock()
    mock_speaker.is_playing = _threading.Event()
    monkeypatch.setattr("heckler.pipeline.Speaker", lambda _: mock_speaker)
    monkeypatch.setattr("heckler.pipeline.Reactor", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("heckler.pipeline.AudioCapture", lambda *a, **kw: MagicMock())
    monkeypatch.setattr(
        "heckler.pipeline.time.sleep",
        lambda _: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    monkeypatch.setattr("heckler.pipeline.threading.Thread", MagicMock())

    main(["--persona", "stage-host"])

    assert len(seen) == 1
    assert seen[0].name == "stage-host"


def test_main_persona_not_found_exits_nonzero(monkeypatch, capsys):
    cfg = HecklerConfig(anthropic_api_key="test-key")
    monkeypatch.setattr("heckler.pipeline.load_config", lambda: cfg)
    monkeypatch.setattr(
        "heckler.pipeline.load_persona",
        lambda _path: (_ for _ in ()).throw(
            PersonaNotFoundError("no such persona bundle")
        ),
    )

    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "[HECKLER] Error:" in captured.out
    assert "no such persona bundle" in captured.out


def test_main_passes_persona_prompts_to_reactor(monkeypatch):
    """``Reactor`` receives resolved ``system_prompt`` and ``examples`` from the loaded persona."""
    cfg = HecklerConfig(anthropic_api_key="test-key")
    ex: list[dict] = [{"role": "user", "content": "x"}]
    fake_persona = Persona(
        name="heckler",
        description="d",
        system_prompt="resolved-system",
        examples=ex,
        config_overrides={},
    )
    reactor_cls = MagicMock(return_value=MagicMock())

    monkeypatch.setattr("heckler.pipeline.load_config", lambda: cfg)
    monkeypatch.setattr("heckler.pipeline.load_persona", lambda _p: fake_persona)
    monkeypatch.setattr(
        "heckler.pipeline.apply_persona_overrides", lambda base, _persona: base
    )
    monkeypatch.setattr("heckler.pipeline.HecklerLogger", lambda _: MagicMock())
    monkeypatch.setattr("heckler.pipeline.Transcriber", lambda _: MagicMock())
    mock_speaker = MagicMock()
    mock_speaker.is_playing = _threading.Event()
    monkeypatch.setattr("heckler.pipeline.Speaker", lambda _: mock_speaker)
    monkeypatch.setattr("heckler.pipeline.Reactor", reactor_cls)
    monkeypatch.setattr("heckler.pipeline.AudioCapture", lambda *a, **kw: MagicMock())
    monkeypatch.setattr(
        "heckler.pipeline.time.sleep",
        lambda _: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    monkeypatch.setattr("heckler.pipeline.threading.Thread", MagicMock())

    main([])

    reactor_cls.assert_called_once_with(cfg, "resolved-system", ex)


def test_main_reactor_receives_post_override_config(monkeypatch):
    """``Reactor`` is constructed with the ``HecklerConfig`` returned by ``apply_persona_overrides``."""
    cfg = HecklerConfig(anthropic_api_key="test-key", llm_model="openai/gpt-4o-mini")
    fake_persona = Persona(
        name="heckler",
        description="",
        system_prompt="s",
        examples=[],
        config_overrides={},
    )
    merged = replace(cfg, llm_model="ollama/custom")
    reactor_cls = MagicMock(return_value=MagicMock())

    monkeypatch.setattr("heckler.pipeline.load_config", lambda: cfg)
    monkeypatch.setattr("heckler.pipeline.load_persona", lambda _p: fake_persona)
    monkeypatch.setattr(
        "heckler.pipeline.apply_persona_overrides", lambda _b, _p: merged
    )
    monkeypatch.setattr("heckler.pipeline.HecklerLogger", lambda _: MagicMock())
    monkeypatch.setattr("heckler.pipeline.Transcriber", lambda _: MagicMock())
    mock_speaker = MagicMock()
    mock_speaker.is_playing = _threading.Event()
    monkeypatch.setattr("heckler.pipeline.Speaker", lambda _: mock_speaker)
    monkeypatch.setattr("heckler.pipeline.Reactor", reactor_cls)
    monkeypatch.setattr("heckler.pipeline.AudioCapture", lambda *a, **kw: MagicMock())
    monkeypatch.setattr(
        "heckler.pipeline.time.sleep",
        lambda _: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    monkeypatch.setattr("heckler.pipeline.threading.Thread", MagicMock())

    main([])

    assert reactor_cls.call_args is not None
    passed_cfg = reactor_cls.call_args[0][0]
    assert passed_cfg.llm_model == "ollama/custom"


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


def test_transcribe_worker_persists_chunks():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    init_transcript_schema(conn)
    create_session(conn, session_id="sid-1", name="n")
    q: queue.Queue = queue.Queue()
    tr = MagicMock()
    tr.transcribe.return_value = "  hello  "
    cfg = HecklerConfig(anthropic_api_key="x", sample_rate=16_000)
    chunk = AudioChunk(audio=np.zeros(16_000, dtype=np.float32), captured_at=0.0)
    q.put(chunk)
    q.put(None)
    _run_transcribe_worker(
        config=cfg,
        audio_queue=q,
        transcriber=tr,
        transcript_conn=conn,
        session_id="sid-1",
        transcript_lock=_threading.Lock(),
    )
    rows = conn.execute(
        "SELECT chunk_text, sequence_num, duration_s FROM transcript_chunks"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "hello"
    assert rows[0][1] == 1
    assert rows[0][2] == pytest.approx(1.0)


def test_transcribe_worker_skips_empty_transcripts():
    """Empty / whitespace-only transcripts must not consume a sequence number or insert rows."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    init_transcript_schema(conn)
    create_session(conn, session_id="sid-e", name="n")
    q: queue.Queue = queue.Queue()
    tr = MagicMock()
    tr.transcribe.return_value = "   "
    cfg = HecklerConfig(anthropic_api_key="x", sample_rate=16_000)
    q.put(
        AudioChunk(audio=np.zeros(100, dtype=np.float32), captured_at=0.0)
    )
    q.put(None)
    _run_transcribe_worker(
        config=cfg,
        audio_queue=q,
        transcriber=tr,
        transcript_conn=conn,
        session_id="sid-e",
        transcript_lock=_threading.Lock(),
    )
    n = conn.execute("SELECT COUNT(*) FROM transcript_chunks").fetchone()[0]
    assert n == 0


def test_transcribe_worker_sentinel_shutdown():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    init_transcript_schema(conn)
    create_session(conn, session_id="sid-2", name="n")
    q: queue.Queue = queue.Queue()
    q.put(None)
    _run_transcribe_worker(
        config=HecklerConfig(anthropic_api_key="x"),
        audio_queue=q,
        transcriber=MagicMock(),
        transcript_conn=conn,
        session_id="sid-2",
        transcript_lock=_threading.Lock(),
    )


def test_main_transcribe_mode_does_not_load_speaker_or_reactor(tmp_path, monkeypatch):
    db_path = tmp_path / "t.db"
    cfg = HecklerConfig(anthropic_api_key="k", sqlite_database_path=str(db_path))
    monkeypatch.setattr("heckler.pipeline.load_config", lambda: cfg)

    def no_persona(*_a, **_k):
        raise AssertionError("load_persona must not run in transcribe mode")

    monkeypatch.setattr("heckler.pipeline.load_persona", no_persona)

    def no_speaker(*_a, **_k):
        raise AssertionError("Speaker must not load in transcribe mode")

    def no_reactor(*_a, **_k):
        raise AssertionError("Reactor must not load in transcribe mode")

    def no_logger(*_a, **_k):
        raise AssertionError("HecklerLogger must not load in transcribe mode")

    def no_ctx(*_a, **_k):
        raise AssertionError("ContextBuffer must not load in transcribe mode")

    def no_pacing(*_a, **_k):
        raise AssertionError("PacingGate must not load in transcribe mode")

    monkeypatch.setattr("heckler.pipeline.Speaker", no_speaker)
    monkeypatch.setattr("heckler.pipeline.Reactor", no_reactor)
    monkeypatch.setattr("heckler.pipeline.HecklerLogger", no_logger)
    monkeypatch.setattr("heckler.pipeline.ContextBuffer", no_ctx)
    monkeypatch.setattr("heckler.pipeline.PacingGate", no_pacing)

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe.return_value = ""
    monkeypatch.setattr("heckler.pipeline.Transcriber", lambda *_a, **_k: mock_transcriber)

    mock_capture = MagicMock()
    monkeypatch.setattr(
        "heckler.pipeline.AudioCapture", lambda *_a, **_k: mock_capture
    )

    monkeypatch.setattr(
        "heckler.pipeline.time.sleep",
        lambda *_a, **_k: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    spawned: list[_threading.Thread] = []
    _OrigThread = _threading.Thread

    class _TrackingThread(_OrigThread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            spawned.append(self)

    monkeypatch.setattr("heckler.pipeline.threading.Thread", _TrackingThread)

    main(["--mode", "transcribe"])

    mock_capture.stop.assert_called_once()
    assert len(spawned) == 1
    assert spawned[0].name == "heckler-transcribe"
    for t in spawned:
        assert not t.is_alive()


def test_main_transcribe_forwards_session_name_to_create_session(tmp_path, monkeypatch):
    db_path = tmp_path / "t.db"
    cfg = HecklerConfig(anthropic_api_key="k", sqlite_database_path=str(db_path))
    monkeypatch.setattr("heckler.pipeline.load_config", lambda: cfg)
    monkeypatch.setattr(
        "heckler.pipeline.load_persona",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("persona path must not run in transcribe mode")
        ),
    )

    seen: dict[str, str] = {}

    def wrap_create(conn, *, session_id, name):
        seen["name"] = name
        from heckler.transcript_store import create_session as real_create

        return real_create(conn, session_id=session_id, name=name)

    monkeypatch.setattr("heckler.pipeline.create_session", wrap_create)

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe.return_value = ""
    monkeypatch.setattr("heckler.pipeline.Transcriber", lambda *_a, **_k: mock_transcriber)
    mock_capture = MagicMock()
    monkeypatch.setattr(
        "heckler.pipeline.AudioCapture", lambda *_a, **_k: mock_capture
    )
    monkeypatch.setattr(
        "heckler.pipeline.time.sleep",
        lambda *_a, **_k: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    monkeypatch.setattr("heckler.pipeline.threading.Thread", MagicMock)

    main(["--mode", "transcribe", "--session-name", "town-hall"])

    assert seen["name"] == "town-hall"


def test_transcribe_mode_passes_vad_overrides_to_audio_capture(monkeypatch):
    cfg = HecklerConfig(
        anthropic_api_key="k",
        max_speech_duration_s=9.0,
        silence_duration_ms=111,
        min_speech_duration_ms=222,
        transcribe_max_speech_duration_s=40.0,
        transcribe_silence_duration_ms=1600,
        transcribe_min_speech_duration_ms=333,
    )
    captured: list[HecklerConfig] = []

    def capture_audio(c: HecklerConfig, *_a, **_k):
        captured.append(c)
        return MagicMock()

    monkeypatch.setattr("heckler.pipeline.load_config", lambda: cfg)
    monkeypatch.setattr("heckler.pipeline.Transcriber", lambda *_a, **_k: MagicMock())
    monkeypatch.setattr(
        "heckler.pipeline.open_store", lambda *_a, **_k: sqlite3.connect(":memory:")
    )
    monkeypatch.setattr("heckler.pipeline.init_transcript_schema", lambda *_a, **_k: None)
    monkeypatch.setattr("heckler.pipeline.create_session", lambda *_a, **_k: MagicMock())
    monkeypatch.setattr("heckler.pipeline.close_session", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "heckler.pipeline.export_session_markdown", lambda *_a, **_k: None
    )
    monkeypatch.setattr("heckler.pipeline.AudioCapture", capture_audio)
    monkeypatch.setattr(
        "heckler.pipeline.time.sleep",
        lambda *_a, **_k: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    monkeypatch.setattr("heckler.pipeline.threading.Thread", MagicMock)

    main(["--mode", "transcribe"])

    assert len(captured) == 1
    eff = captured[0]
    assert eff.max_speech_duration_s == 40.0
    assert eff.silence_duration_ms == 1600
    assert eff.min_speech_duration_ms == 333


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
