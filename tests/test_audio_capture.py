import dataclasses
import queue
import threading

import numpy as np
import pytest

from heckler.audio_capture import (
    VAD_FRAME_SAMPLES,
    _put_drop_oldest,
    AudioCapture,
    play_gate_frame_tick,
)
from heckler.config import HecklerConfig
from heckler.models import AudioChunk


def test_play_gate_frame_tick_clears_while_playing():
    seg = [np.zeros(VAD_FRAME_SAMPLES, dtype=np.float32)]
    result = play_gate_frame_tick(True, False, True, seg)
    assert result.capturing is False
    assert result.segment == []
    assert result.was_gated is True
    assert result.reset_vad is False


def test_play_gate_frame_tick_reset_vad_on_clear_edge():
    seg = [np.zeros(VAD_FRAME_SAMPLES, dtype=np.float32)]
    result = play_gate_frame_tick(False, True, True, seg)
    assert result.capturing is True
    assert len(result.segment) == 1
    assert result.was_gated is False
    assert result.reset_vad is True


def test_play_gate_frame_tick_passthrough_when_open():
    result = play_gate_frame_tick(False, False, False, [])
    assert result.capturing is False
    assert result.segment == []
    assert result.was_gated is False
    assert result.reset_vad is False


def test_put_drop_oldest_removes_oldest_on_overflow():
    q: queue.Queue[str] = queue.Queue(maxsize=2)
    q.put_nowait("a")
    q.put_nowait("b")
    _put_drop_oldest(q, "c")
    assert q.qsize() == 2
    assert q.get_nowait() == "b"
    assert q.get_nowait() == "c"


def test_capture_loop_rejects_non_16khz():
    cfg = dataclasses.replace(HecklerConfig(), sample_rate=8_000)
    cap = AudioCapture(cfg, queue.Queue(), threading.Event())
    with pytest.raises(ValueError, match="16000"):
        cap._capture_loop()


def test_vad_callback_enqueues_mono_float32():
    cap = AudioCapture(HecklerConfig(), queue.Queue(), threading.Event())
    block = np.zeros((VAD_FRAME_SAMPLES, 1), dtype=np.float32)
    cap._vad_callback(block, VAD_FRAME_SAMPLES, None, None)
    drained = cap._drain_pcm_batch()
    assert len(drained) == 1
    assert drained[0].dtype == np.float32
    assert drained[0].shape == (VAD_FRAME_SAMPLES,)


def test_emit_skips_when_speaker_is_playing():
    cfg = HecklerConfig()
    out: queue.Queue[AudioChunk] = queue.Queue()
    playing = threading.Event()
    playing.set()
    cap = AudioCapture(cfg, out, playing)
    audio = np.ones(int(cfg.sample_rate * cfg.min_speech_duration_ms / 1000), dtype=np.float32)
    cap._emit_audio_segment(audio, int(cfg.sample_rate * cfg.min_speech_duration_ms / 1000))
    assert out.empty()


def test_emit_enqueues_when_not_playing():
    cfg = HecklerConfig()
    out: queue.Queue[AudioChunk] = queue.Queue()
    cap = AudioCapture(cfg, out, threading.Event())
    n = int(cfg.sample_rate * cfg.min_speech_duration_ms / 1000)
    audio = np.ones(n, dtype=np.float32)
    cap._emit_audio_segment(audio, n)
    chunk = out.get_nowait()
    assert isinstance(chunk, AudioChunk)
    assert chunk.audio.dtype == np.float32
    assert chunk.audio.shape == (n,)


def test_emit_rejects_non_float32_or_multidim():
    cfg = HecklerConfig()
    cap = AudioCapture(cfg, queue.Queue(), threading.Event())
    n = int(cfg.sample_rate * cfg.min_speech_duration_ms / 1000)
    with pytest.raises(TypeError):
        cap._emit_audio_segment(np.ones(n, dtype=np.float64), n)
    with pytest.raises(TypeError):
        cap._emit_audio_segment(np.ones((n, 1), dtype=np.float32), n)


def test_emit_respects_min_speech_duration():
    cfg = HecklerConfig()
    out: queue.Queue[AudioChunk] = queue.Queue()
    cap = AudioCapture(cfg, out, threading.Event())
    min_samples = int(cfg.sample_rate * cfg.min_speech_duration_ms / 1000)
    short = np.ones(min_samples - 1, dtype=np.float32)
    cap._emit_audio_segment(short, min_samples)
    assert out.empty()


def test_emit_on_full_queue_drops_oldest_chunk():
    """Falsifier: overflow policy must evict the oldest chunk, not refuse the newest."""
    cfg = HecklerConfig()
    out: queue.Queue[AudioChunk] = queue.Queue(maxsize=1)
    cap = AudioCapture(cfg, out, threading.Event())
    n = int(cfg.sample_rate * cfg.min_speech_duration_ms / 1000)
    cap._emit_audio_segment(np.ones(n, dtype=np.float32), n)
    cap._emit_audio_segment(np.full(n, 2.0, dtype=np.float32), n)
    assert out.qsize() == 1
    assert out.get_nowait().audio[0] == pytest.approx(2.0)
