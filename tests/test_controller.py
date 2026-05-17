"""Tests for PipelineController, ReactorHolder, and ControllerCallbacks (T1)."""

from __future__ import annotations

import queue
import re
import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from heckler.config import HecklerConfig
from heckler.controller import (
    ControllerCallbacks,
    PipelineAlreadyRunningError,
    PipelineController,
    PipelineNotRunningError,
    ReactorHolder,
)
from heckler.models import AudioChunk, CommentType, ReactorResult, Utterance
from heckler.persona import Persona


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_callbacks(**overrides) -> ControllerCallbacks:
    """ControllerCallbacks with no-op defaults."""
    defaults = dict(
        on_transcript=MagicMock(),
        on_reaction=MagicMock(),
        on_status=MagicMock(),
        on_error=MagicMock(),
    )
    defaults.update(overrides)
    return ControllerCallbacks(**defaults)  # type: ignore[arg-type]


def _make_reactor_result() -> ReactorResult:
    return ReactorResult(
        comment="Nice try.",
        score=0.85,
        comment_type=CommentType.SARCASM,
        raw_response="{}",
    )


def _fake_persona(name: str = "heckler") -> Persona:
    return Persona(
        name=name,
        description="",
        system_prompt="You are heckler.",
        examples=[],
        config_overrides={},
    )


def _audio_utt(transcript: str) -> Utterance:
    chunk = AudioChunk(audio=np.zeros(8, dtype=np.float32), captured_at=0.0)
    return Utterance(
        utterance_id="u1",
        transcript=transcript,
        semantic_density=0.5,
        transcribed_at=1.0,
        audio_chunk=chunk,
    )


# ---------------------------------------------------------------------------
# ReactorHolder tests
# ---------------------------------------------------------------------------


def test_reactor_holder_get_returns_initial_reactor():
    mock_reactor = MagicMock()
    holder = ReactorHolder(mock_reactor)
    assert holder.get() is mock_reactor


def test_reactor_holder_swap():
    """swap() atomically replaces the reactor; subsequent get() returns the new one."""
    old_reactor = MagicMock(name="old")
    new_reactor = MagicMock(name="new")
    holder = ReactorHolder(old_reactor)
    assert holder.get() is old_reactor
    holder.swap(new_reactor)
    assert holder.get() is new_reactor


def test_reactor_holder_swap_thread_safety():
    """Multiple concurrent swaps do not corrupt the holder (lock serialises access)."""
    reactor_a = MagicMock(name="a")
    reactor_b = MagicMock(name="b")
    holder = ReactorHolder(reactor_a)
    errors: list[Exception] = []

    def swapper() -> None:
        try:
            for _ in range(200):
                holder.swap(reactor_b)
                _ = holder.get()
                holder.swap(reactor_a)
                _ = holder.get()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=swapper) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread-safety violations: {errors}"
    assert holder.get() in (reactor_a, reactor_b)


# ---------------------------------------------------------------------------
# ControllerCallbacks dataclass
# ---------------------------------------------------------------------------


def test_callbacks_dataclass_fields():
    """ControllerCallbacks is a dataclass with the four required fields."""
    cb = _make_callbacks()
    assert callable(cb.on_transcript)
    assert callable(cb.on_reaction)
    assert callable(cb.on_status)
    assert callable(cb.on_error)


# ---------------------------------------------------------------------------
# PipelineController — lifecycle (start / stop)
# ---------------------------------------------------------------------------


def _build_controller_mocks(monkeypatch, cfg: HecklerConfig, callbacks: ControllerCallbacks):
    """
    Patch all heavy dependencies so PipelineController.start/stop is unit-testable.
    Returns a dict of mocks for assertions.
    """
    mock_transcriber = MagicMock(name="transcriber")
    mock_speaker = MagicMock(name="speaker")
    mock_speaker.is_playing = threading.Event()
    mock_capture = MagicMock(name="capture")
    mock_reactor = MagicMock(name="reactor")
    fake_persona = _fake_persona()

    monkeypatch.setattr("heckler.controller.Transcriber", lambda _cfg: mock_transcriber)
    monkeypatch.setattr("heckler.controller.Speaker", lambda _cfg: mock_speaker)
    monkeypatch.setattr("heckler.controller.AudioCapture", lambda *a, **kw: mock_capture)
    monkeypatch.setattr("heckler.controller.Reactor", lambda *a, **kw: mock_reactor)
    monkeypatch.setattr("heckler.controller.load_persona", lambda _path: fake_persona)
    monkeypatch.setattr(
        "heckler.controller.apply_persona_overrides", lambda base, _p: base
    )
    monkeypatch.setattr("heckler.controller.HecklerLogger", lambda _: MagicMock())

    return {
        "transcriber": mock_transcriber,
        "speaker": mock_speaker,
        "capture": mock_capture,
        "reactor": mock_reactor,
    }


def test_load_models_transcribe_skips_speaker(monkeypatch):
    cfg = HecklerConfig(anthropic_api_key="k")
    callbacks = _make_callbacks()
    mocks = _build_controller_mocks(monkeypatch, cfg, callbacks)

    ctrl = PipelineController(cfg, callbacks)
    ctrl.load_models(mode="transcribe")

    assert ctrl._transcriber is mocks["transcriber"]
    assert ctrl._speaker is None


def test_load_models_persona_loads_speaker(monkeypatch):
    """Default ``load_models()`` loads Transcriber and Speaker (GUI / persona stack)."""
    cfg = HecklerConfig(anthropic_api_key="k")
    callbacks = _make_callbacks()
    mocks = _build_controller_mocks(monkeypatch, cfg, callbacks)

    ctrl = PipelineController(cfg, callbacks)
    ctrl.load_models()

    assert ctrl._transcriber is mocks["transcriber"]
    assert ctrl._speaker is mocks["speaker"]


def test_on_progress_includes_cuda_and_timing(monkeypatch):
    cfg = HecklerConfig(anthropic_api_key="k")
    callbacks = _make_callbacks()
    _build_controller_mocks(monkeypatch, cfg, callbacks)

    messages: list[str] = []
    ctrl = PipelineController(cfg, callbacks)
    ctrl.load_models(on_progress=messages.append)

    assert any("/ CUDA" in m for m in messages)
    assert any(re.search(r"\(\d+\.\d+s\)", m) for m in messages)
    assert any("Kokoro /" in m for m in messages)


def test_on_status_persona_mic_open(monkeypatch):
    cfg = HecklerConfig(anthropic_api_key="k")
    callbacks = _make_callbacks()
    _build_controller_mocks(monkeypatch, cfg, callbacks)

    ctrl = PipelineController(cfg, callbacks)
    ctrl.load_models()
    ctrl.start(mode="persona")

    status_texts = [c.args[0] for c in callbacks.on_status.call_args_list]
    assert "Mic open. Listening." in status_texts
    assert not any("Running in" in s for s in status_texts)


def test_on_status_transcribe_mic_open(monkeypatch, tmp_path):
    db_path = tmp_path / "t.db"
    cfg = HecklerConfig(anthropic_api_key="k", sqlite_database_path=str(db_path))
    callbacks = _make_callbacks()
    _build_controller_mocks(monkeypatch, cfg, callbacks)

    monkeypatch.setattr(
        "heckler.controller.open_store",
        lambda _p: __import__("sqlite3").connect(":memory:", check_same_thread=False),
    )
    monkeypatch.setattr("heckler.controller.init_transcript_schema", lambda _c: None)
    monkeypatch.setattr("heckler.controller.create_session", lambda *a, **kw: None)
    monkeypatch.setattr("heckler.controller.close_session", lambda *a, **kw: None)
    monkeypatch.setattr("heckler.controller.export_session_markdown", lambda *a, **kw: None)

    ctrl = PipelineController(cfg, callbacks)
    ctrl.load_models(mode="transcribe")
    ctrl.start(mode="transcribe")

    status_texts = [c.args[0] for c in callbacks.on_status.call_args_list]
    assert any("Transcribe mode" in s and "mic open" in s.lower() for s in status_texts)
    assert not any("Running in" in s for s in status_texts)


def test_on_status_transcribe_session_ended_on_stop(monkeypatch, tmp_path):
    """``stop()`` after transcribe mode emits session-ended status with id and markdown path."""
    db_path = tmp_path / "t.db"
    cfg = HecklerConfig(anthropic_api_key="k", sqlite_database_path=str(db_path))
    callbacks = _make_callbacks()
    _build_controller_mocks(monkeypatch, cfg, callbacks)

    monkeypatch.setattr(
        "heckler.controller.open_store",
        lambda _p: __import__("sqlite3").connect(":memory:", check_same_thread=False),
    )
    monkeypatch.setattr("heckler.controller.init_transcript_schema", lambda _c: None)
    monkeypatch.setattr("heckler.controller.create_session", lambda *a, **kw: None)
    monkeypatch.setattr("heckler.controller.close_session", lambda *a, **kw: None)
    monkeypatch.setattr("heckler.controller.export_session_markdown", lambda *a, **kw: None)

    ctrl = PipelineController(cfg, callbacks)
    ctrl.load_models(mode="transcribe")
    ctrl.start(mode="transcribe", session_name="my-session")
    session_id = ctrl._transcript_session_id
    assert session_id is not None
    ctrl.stop()

    status_texts = [c.args[0] for c in callbacks.on_status.call_args_list]
    ended = [s for s in status_texts if "Transcribe session ended" in s]
    assert len(ended) == 1
    assert session_id in ended[0]
    assert "markdown=" in ended[0]


def test_controller_start_stop(monkeypatch):
    """PipelineController starts and stops cleanly; is_running reflects state."""
    cfg = HecklerConfig(anthropic_api_key="k")
    callbacks = _make_callbacks()
    mocks = _build_controller_mocks(monkeypatch, cfg, callbacks)

    ctrl = PipelineController(cfg, callbacks)
    ctrl.load_models()

    assert not ctrl.is_running
    ctrl.start(mode="persona")
    assert ctrl.is_running
    assert ctrl.current_mode == "persona"

    ctrl.stop()
    assert not ctrl.is_running
    assert ctrl.current_mode == "persona"  # mode retained after stop

    mocks["capture"].stop.assert_called_once()


def test_controller_start_already_running_raises(monkeypatch):
    cfg = HecklerConfig(anthropic_api_key="k")
    callbacks = _make_callbacks()
    _build_controller_mocks(monkeypatch, cfg, callbacks)

    ctrl = PipelineController(cfg, callbacks)
    ctrl.load_models()
    ctrl.start(mode="persona")

    with pytest.raises(PipelineAlreadyRunningError):
        ctrl.start(mode="persona")

    ctrl.stop()


def test_controller_stop_idempotent(monkeypatch):
    """Calling stop() when not running is a no-op (no exception)."""
    cfg = HecklerConfig(anthropic_api_key="k")
    callbacks = _make_callbacks()
    _build_controller_mocks(monkeypatch, cfg, callbacks)

    ctrl = PipelineController(cfg, callbacks)
    ctrl.load_models()
    ctrl.stop()  # not running — must not raise
    ctrl.stop()  # second call — still must not raise


def test_controller_on_status_called_on_start_and_stop(monkeypatch):
    cfg = HecklerConfig(anthropic_api_key="k")
    callbacks = _make_callbacks()
    _build_controller_mocks(monkeypatch, cfg, callbacks)

    ctrl = PipelineController(cfg, callbacks)
    ctrl.load_models()
    ctrl.start(mode="persona")
    ctrl.stop()

    status_calls = [call.args[0] for call in callbacks.on_status.call_args_list]
    assert any("Mic open" in s or "Listening" in s for s in status_calls)
    assert any("Stopping" in s for s in status_calls)


# ---------------------------------------------------------------------------
# PipelineController — callback invocation on transcript
# ---------------------------------------------------------------------------


def test_callbacks_invoked_on_transcript(monkeypatch):
    """on_transcript fires when a transcript passes the density gate (persona mode)."""
    cfg = HecklerConfig(anthropic_api_key="k")
    received: list[str] = []
    callbacks = _make_callbacks(on_transcript=received.append)

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe.side_effect = ["hello world enough words pass"]
    mock_speaker = MagicMock()
    mock_speaker.is_playing = threading.Event()
    mock_capture = MagicMock()
    mock_reactor = MagicMock()
    fake_persona = _fake_persona()

    monkeypatch.setattr("heckler.controller.Transcriber", lambda _cfg: mock_transcriber)
    monkeypatch.setattr("heckler.controller.Speaker", lambda _cfg: mock_speaker)
    monkeypatch.setattr("heckler.controller.AudioCapture", lambda *a, **kw: mock_capture)
    monkeypatch.setattr("heckler.controller.Reactor", lambda *a, **kw: mock_reactor)
    monkeypatch.setattr("heckler.controller.load_persona", lambda _path: fake_persona)
    monkeypatch.setattr("heckler.controller.apply_persona_overrides", lambda base, _p: base)
    monkeypatch.setattr("heckler.controller.HecklerLogger", lambda _: MagicMock())

    # Drive the transcription worker directly to avoid real audio hardware
    from heckler.pipeline import _run_transcription_worker
    from heckler.models import AudioChunk

    chunk = AudioChunk(audio=np.zeros(8, dtype=np.float32), captured_at=0.0)
    aq: queue.Queue = queue.Queue()
    rq: queue.Queue = queue.Queue()
    aq.put(chunk)
    aq.put(None)

    _run_transcription_worker(
        config=cfg,
        audio_queue=aq,
        reaction_queue=rq,
        transcriber=mock_transcriber,
        heckler_logger=MagicMock(),
        on_transcript=received.append,
    )

    assert len(received) == 1
    assert "hello" in received[0]


# ---------------------------------------------------------------------------
# PipelineController — hot-swap (swap_persona)
# ---------------------------------------------------------------------------


def test_reactor_holder_swap_changes_reactor_seen_by_worker():
    """
    ReactorHolder.swap atomically replaces the reactor reference.
    A worker calling holder.get() after the swap sees the new reactor.
    This is the core correctness guarantee of the hot-swap protocol.
    """
    original = MagicMock(name="original-reactor")
    replacement = MagicMock(name="replacement-reactor")
    holder = ReactorHolder(original)

    # Simulate a worker iteration: get reactor, start react call
    r1 = holder.get()
    assert r1 is original

    # GUI thread swaps while worker holds reference
    holder.swap(replacement)

    # r1 still points to original — in-progress call completes with old reactor (correct)
    assert r1 is original

    # Next worker iteration picks up the new reactor
    r2 = holder.get()
    assert r2 is replacement


def test_swap_persona_not_running_raises(monkeypatch):
    cfg = HecklerConfig(anthropic_api_key="k")
    callbacks = _make_callbacks()

    ctrl = PipelineController(cfg, callbacks)
    with pytest.raises(PipelineNotRunningError):
        ctrl.swap_persona("other")


def test_swap_persona_while_running(monkeypatch):
    """swap_persona replaces the ReactorHolder's Reactor while the pipeline runs."""
    cfg = HecklerConfig(anthropic_api_key="k")
    callbacks = _make_callbacks()

    mock_transcriber = MagicMock()
    mock_speaker = MagicMock()
    mock_speaker.is_playing = threading.Event()
    mock_capture = MagicMock()
    original_reactor = MagicMock(name="original")
    new_reactor = MagicMock(name="new")
    fake_persona_orig = _fake_persona("heckler")
    fake_persona_new = _fake_persona("stage-host")

    reactor_instances: list[Any] = [original_reactor, new_reactor]
    reactor_call_count = {"n": 0}

    def _make_reactor(*a, **kw):
        idx = reactor_call_count["n"]
        reactor_call_count["n"] += 1
        return reactor_instances[idx] if idx < len(reactor_instances) else MagicMock()

    personas = {"heckler": fake_persona_orig, "stage-host": fake_persona_new}

    monkeypatch.setattr("heckler.controller.Transcriber", lambda _: mock_transcriber)
    monkeypatch.setattr("heckler.controller.Speaker", lambda _: mock_speaker)
    monkeypatch.setattr("heckler.controller.AudioCapture", lambda *a, **kw: mock_capture)
    monkeypatch.setattr("heckler.controller.Reactor", _make_reactor)
    monkeypatch.setattr(
        "heckler.controller.load_persona",
        lambda path: personas[path.name],
    )
    monkeypatch.setattr("heckler.controller.apply_persona_overrides", lambda base, _p: base)
    monkeypatch.setattr("heckler.controller.HecklerLogger", lambda _: MagicMock())

    ctrl = PipelineController(cfg, callbacks)
    ctrl.load_models()
    ctrl.start(mode="persona", persona_name="heckler")

    assert ctrl._reactor_holder is not None
    assert ctrl._reactor_holder.get() is original_reactor

    ctrl.swap_persona("stage-host")

    assert ctrl._reactor_holder.get() is new_reactor
    assert ctrl.current_persona_name == "stage-host"

    ctrl.stop()


# ---------------------------------------------------------------------------
# PipelineController — mode switch
# ---------------------------------------------------------------------------


def test_switch_mode_not_running_raises(monkeypatch):
    cfg = HecklerConfig(anthropic_api_key="k")
    ctrl = PipelineController(cfg, _make_callbacks())
    with pytest.raises(PipelineNotRunningError):
        ctrl.switch_mode("transcribe")


def test_switch_mode_rebuilds_topology(monkeypatch, tmp_path):
    """switch_mode stops the running pipeline and restarts in the new mode."""
    db_path = tmp_path / "t.db"
    cfg = HecklerConfig(anthropic_api_key="k", sqlite_database_path=str(db_path))
    callbacks = _make_callbacks()
    _build_controller_mocks(monkeypatch, cfg, callbacks)

    monkeypatch.setattr(
        "heckler.controller.open_store",
        lambda _p: __import__("sqlite3").connect(":memory:", check_same_thread=False),
    )
    monkeypatch.setattr("heckler.controller.init_transcript_schema", lambda _c: None)
    monkeypatch.setattr("heckler.controller.create_session", lambda *a, **kw: None)
    monkeypatch.setattr("heckler.controller.close_session", lambda *a, **kw: None)
    monkeypatch.setattr("heckler.controller.export_session_markdown", lambda *a, **kw: None)

    ctrl = PipelineController(cfg, callbacks)
    ctrl.load_models()
    ctrl.start(mode="persona")
    assert ctrl.current_mode == "persona"

    ctrl.switch_mode("transcribe")
    assert ctrl.is_running
    assert ctrl.current_mode == "transcribe"

    ctrl.stop()


# ---------------------------------------------------------------------------
# PipelineController — error conditions
# ---------------------------------------------------------------------------


def test_pipeline_not_running_error_is_runtime_error():
    assert issubclass(PipelineNotRunningError, RuntimeError)


def test_pipeline_already_running_error_is_runtime_error():
    assert issubclass(PipelineAlreadyRunningError, RuntimeError)


# ---------------------------------------------------------------------------
# Adversarial micro-pass
# ---------------------------------------------------------------------------


def test_on_reaction_callback_not_fired_on_llm_error():
    """
    on_reaction must NOT fire when reactor.react() returns (None, latency, LLM_ERROR).
    Failure mode not covered by other tests: callback invoked even for discarded utterances.
    """
    from heckler.pipeline import _run_reaction_worker
    from heckler.models import DiscardReason

    rq: queue.Queue = queue.Queue()
    rq.put(_audio_utt("test"))
    rq.put(None)

    reactor = MagicMock()
    reactor.react.return_value = (None, 10.0, DiscardReason.LLM_ERROR)

    on_reaction = MagicMock()
    context_buffer = MagicMock()
    context_buffer.get_context_block.return_value = ""

    _run_reaction_worker(
        context_buffer=context_buffer,
        reactor_holder=ReactorHolder(reactor),
        pacing_gate=MagicMock(),
        speaker=MagicMock(),
        heckler_logger=MagicMock(),
        reaction_queue=rq,
        on_reaction=on_reaction,
    )

    on_reaction.assert_not_called()


def test_on_reaction_callback_fires_with_was_spoken_true_on_success():
    """Spoken reaction fires on_reaction with was_spoken=True."""
    from heckler.pipeline import _run_reaction_worker
    from heckler.models import DiscardReason

    rq: queue.Queue = queue.Queue()
    rq.put(_audio_utt("good utterance"))
    rq.put(None)

    rr = _make_reactor_result()
    reactor = MagicMock()
    reactor.react.return_value = (rr, 5.0, None)

    pacing = MagicMock()
    pacing.evaluate.return_value = (True, 0.0)

    speaker = MagicMock()
    speaker.speak.return_value = 42.0

    received: list[tuple] = []
    context_buffer = MagicMock()
    context_buffer.get_context_block.return_value = ""

    _run_reaction_worker(
        context_buffer=context_buffer,
        reactor_holder=ReactorHolder(reactor),
        pacing_gate=pacing,
        speaker=speaker,
        heckler_logger=MagicMock(),
        reaction_queue=rq,
        on_reaction=lambda res, spoken: received.append((res, spoken)),
    )

    assert len(received) == 1
    assert received[0] == (rr, True)


def test_on_reaction_callback_fires_with_was_spoken_false_on_pacing_gate():
    """Pacing-gated reaction fires on_reaction with was_spoken=False."""
    from heckler.pipeline import _run_reaction_worker

    rq: queue.Queue = queue.Queue()
    rq.put(_audio_utt("too frequent"))
    rq.put(None)

    rr = _make_reactor_result()
    reactor = MagicMock()
    reactor.react.return_value = (rr, 5.0, None)

    pacing = MagicMock()
    pacing.evaluate.return_value = (False, 8.0)

    received: list[tuple] = []
    context_buffer = MagicMock()
    context_buffer.get_context_block.return_value = ""

    _run_reaction_worker(
        context_buffer=context_buffer,
        reactor_holder=ReactorHolder(reactor),
        pacing_gate=pacing,
        speaker=MagicMock(),
        heckler_logger=MagicMock(),
        reaction_queue=rq,
        on_reaction=lambda res, spoken: received.append((res, spoken)),
    )

    assert len(received) == 1
    assert received[0] == (rr, False)


def test_on_transcript_callback_exception_does_not_kill_worker():
    """A raising on_transcript callback must not terminate the transcription worker."""
    from heckler.pipeline import _run_transcription_worker
    from heckler.models import AudioChunk

    chunk = AudioChunk(audio=np.zeros(8, dtype=np.float32), captured_at=0.0)
    aq: queue.Queue = queue.Queue()
    rq: queue.Queue = queue.Queue()
    aq.put(chunk)
    aq.put(chunk)
    aq.put(None)

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe.return_value = "hello world enough words pass"

    call_count = {"n": 0}

    def boom(text: str) -> None:
        call_count["n"] += 1
        raise RuntimeError("callback exploded")

    _run_transcription_worker(
        config=HecklerConfig(anthropic_api_key="k"),
        audio_queue=aq,
        reaction_queue=rq,
        transcriber=mock_transcriber,
        heckler_logger=MagicMock(),
        on_transcript=boom,
    )

    assert call_count["n"] == 2, "callback must fire for every passing transcript"
    # Worker processed both items — did not die on the first exception
