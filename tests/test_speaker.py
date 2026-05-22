import dataclasses
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import kokoro
import numpy as np
import pytest
import torch

import heckler.speaker as speaker_mod
from heckler.config import HecklerConfig, apply_resolved_locale
from heckler.speaker import Speaker, SpeakerError


@pytest.fixture
def config() -> HecklerConfig:
    return dataclasses.replace(HecklerConfig(), tts_gate_tail_ms=0)


def _speaker_with_mock_pipeline(monkeypatch, config: HecklerConfig):
    mock_cls = MagicMock()
    pipeline_inst = MagicMock()
    mock_cls.return_value = pipeline_inst
    monkeypatch.setattr(kokoro, "KPipeline", mock_cls)
    speaker = Speaker(config)
    return speaker, pipeline_inst, mock_cls


def test_init_uses_config_kokoro_lang_code_and_creates_playing_event(monkeypatch, config):
    mock_kp = MagicMock()
    monkeypatch.setattr(kokoro, "KPipeline", mock_kp)
    speaker = Speaker(config)
    mock_kp.assert_called_once_with(lang_code=config.kokoro_lang_code)
    assert isinstance(speaker.is_playing, threading.Event)


@pytest.mark.parametrize(
    ("locale", "expected_lang_code"),
    [("en", "a"), ("en-gb", "b"), ("es", "e")],
)
def test_init_passes_resolved_kokoro_lang_code_to_pipeline(
    monkeypatch, locale, expected_lang_code
):
    cfg = apply_resolved_locale(dataclasses.replace(HecklerConfig(), locale=locale))
    mock_kp = MagicMock()
    monkeypatch.setattr(kokoro, "KPipeline", mock_kp)
    Speaker(cfg)
    mock_kp.assert_called_once_with(lang_code=expected_lang_code)


def test_init_logs_download_before_pipeline_construct(monkeypatch, config):
    mock_kp = MagicMock()
    mock_info = MagicMock()
    monkeypatch.setattr(kokoro, "KPipeline", mock_kp)
    monkeypatch.setattr(speaker_mod.logger, "info", mock_info)
    Speaker(config)
    mock_info.assert_called()
    assert any(
        "downloading TTS model" in (c.args[0] if c.args else "")
        for c in mock_info.call_args_list
    )
    mock_kp.assert_called_once()


def test_speak_sets_mic_gate_before_pipeline_call(monkeypatch, config):
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    monkeypatch.setattr(speaker_mod.sd, "play", MagicMock())
    order: list[str] = []

    def fake_call(*_a, **_k):
        order.append("pipeline")
        return iter([("g", "p", np.array([0.1, -0.1], dtype=np.float32))])

    pipeline_inst.side_effect = fake_call

    real_set = speaker.is_playing.set

    def track_set() -> None:
        order.append("set")
        real_set()

    speaker.is_playing.set = track_set  # type: ignore[method-assign]

    speaker.speak("hello")

    assert order.index("set") < order.index("pipeline")


def test_speak_passes_voice_speed_and_plays_at_24k(monkeypatch, config):
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    mock_play = MagicMock()
    monkeypatch.setattr(speaker_mod.sd, "play", mock_play)
    pipeline_inst.side_effect = lambda *a, **k: iter(
        [("g", "p", np.array([0.05], dtype=np.float32))]
    )

    speaker.speak("line")

    pipeline_inst.assert_called_once_with(
        "line", voice=config.kokoro_voice, speed=config.kokoro_speed
    )
    kwargs = mock_play.call_args.kwargs
    assert kwargs["samplerate"] == 24000
    assert kwargs["blocking"] is True


def test_speak_clears_event_after_successful_playback(monkeypatch, config):
    assert config.tts_gate_tail_ms == 0
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    monkeypatch.setattr(speaker_mod.sd, "play", MagicMock())
    pipeline_inst.side_effect = lambda *a, **k: iter(
        [("g", "p", np.array([0.01], dtype=np.float32))]
    )

    speaker.speak("ok")

    assert not speaker.is_playing.is_set()


def test_synthesis_failure_clears_event_and_raises_speaker_error(monkeypatch, config):
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    monkeypatch.setattr(speaker_mod.sd, "play", MagicMock())
    pipeline_inst.side_effect = RuntimeError("synth failed")

    with pytest.raises(SpeakerError, match="TTS synthesis failed"):
        speaker.speak("x")

    assert not speaker.is_playing.is_set()


def test_play_failure_still_clears_event(monkeypatch, config):
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    mock_play = MagicMock()
    mock_play.side_effect = OSError("device")
    monkeypatch.setattr(speaker_mod.sd, "play", mock_play)
    pipeline_inst.side_effect = lambda *a, **k: iter(
        [("g", "p", np.array([0.01], dtype=np.float32))]
    )

    with pytest.raises(OSError, match="device"):
        speaker.speak("x")

    assert not speaker.is_playing.is_set()


def test_malformed_kokoro_tuple_raises_speaker_error(monkeypatch, config):
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    monkeypatch.setattr(speaker_mod.sd, "play", MagicMock())
    pipeline_inst.side_effect = lambda *a, **k: iter([("not", "a triple")])

    with pytest.raises(SpeakerError):
        speaker.speak("x")

    assert not speaker.is_playing.is_set()


def test_non_ndarray_audio_chunk_raises_speaker_error(monkeypatch, config):
    """Falsifier: list payloads must not pass collection silently."""
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    monkeypatch.setattr(speaker_mod.sd, "play", MagicMock())
    pipeline_inst.side_effect = lambda *a, **k: iter([("g", "p", [0.1, 0.2])])

    with pytest.raises(SpeakerError):
        speaker.speak("x")

    assert not speaker.is_playing.is_set()


def test_speak_accepts_kokoro_result_like_with_torch_audio(monkeypatch, config):
    """Kokoro >=0.9 yields Result objects with torch.FloatTensor audio, not 3-tuples."""
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    mock_play = MagicMock()
    monkeypatch.setattr(speaker_mod.sd, "play", mock_play)
    fake = SimpleNamespace(audio=torch.tensor([0.5, -0.5], dtype=torch.float32))
    pipeline_inst.side_effect = lambda *a, **k: iter([fake])

    speaker.speak("line")

    played = mock_play.call_args.args[0]
    assert played.dtype == np.float32
    np.testing.assert_array_equal(played, np.array([0.5, -0.5], dtype=np.float32))


def test_empty_kokoro_stream_raises_speaker_error(monkeypatch, config):
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    monkeypatch.setattr(speaker_mod.sd, "play", MagicMock())
    pipeline_inst.side_effect = lambda *a, **k: iter([])

    with pytest.raises(SpeakerError):
        speaker.speak("x")

    assert not speaker.is_playing.is_set()


def test_speak_concatenates_multiple_kokoro_chunks(monkeypatch, config):
    """Falsifier: multi-chunk streams must play as one contiguous buffer."""
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    mock_play = MagicMock()
    monkeypatch.setattr(speaker_mod.sd, "play", mock_play)
    pipeline_inst.side_effect = lambda *a, **k: iter(
        [
            ("g1", "p1", np.array([1.0], dtype=np.float32)),
            ("g2", "p2", np.array([2.0, 3.0], dtype=np.float32)),
        ]
    )

    speaker.speak("text")

    played = mock_play.call_args.args[0]
    assert played.shape == (3,)
    assert played.dtype == np.float32
    np.testing.assert_array_equal(played, np.array([1.0, 2.0, 3.0], dtype=np.float32))


def test_speak_holds_mic_gate_during_post_playback_tail(monkeypatch):
    config = dataclasses.replace(HecklerConfig(), tts_gate_tail_ms=400)
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    monkeypatch.setattr(speaker_mod.sd, "play", MagicMock())
    pipeline_inst.side_effect = lambda *a, **k: iter(
        [("g", "p", np.array([0.01], dtype=np.float32))]
    )
    gate_during_tail: list[bool] = []
    sleep_seconds: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_seconds.append(seconds)
        gate_during_tail.append(speaker.is_playing.is_set())

    monkeypatch.setattr(speaker_mod.time, "sleep", fake_sleep)

    speaker.speak("ok")

    assert gate_during_tail == [True]
    assert sleep_seconds == [0.4]
    assert not speaker.is_playing.is_set()


def test_speak_zero_tail_skips_post_playback_sleep(monkeypatch, config):
    assert config.tts_gate_tail_ms == 0
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    monkeypatch.setattr(speaker_mod.sd, "play", MagicMock())
    pipeline_inst.side_effect = lambda *a, **k: iter(
        [("g", "p", np.array([0.01], dtype=np.float32))]
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        speaker_mod.time, "sleep", lambda s: sleep_calls.append(s)
    )

    speaker.speak("ok")

    assert sleep_calls == []


def test_play_failure_skips_post_playback_tail_sleep(monkeypatch, config):
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    mock_play = MagicMock()
    mock_play.side_effect = OSError("device")
    monkeypatch.setattr(speaker_mod.sd, "play", mock_play)
    pipeline_inst.side_effect = lambda *a, **k: iter(
        [("g", "p", np.array([0.01], dtype=np.float32))]
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        speaker_mod.time, "sleep", lambda s: sleep_calls.append(s)
    )

    with pytest.raises(OSError, match="device"):
        speaker.speak("x")

    assert sleep_calls == []


def test_synthesis_failure_skips_post_playback_tail_sleep(monkeypatch, config):
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    monkeypatch.setattr(speaker_mod.sd, "play", MagicMock())
    pipeline_inst.side_effect = RuntimeError("synth failed")
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        speaker_mod.time, "sleep", lambda s: sleep_calls.append(s)
    )

    with pytest.raises(SpeakerError, match="TTS synthesis failed"):
        speaker.speak("x")

    assert sleep_calls == []


def test_speak_tts_latency_excludes_post_playback_tail(monkeypatch):
    config = dataclasses.replace(HecklerConfig(), tts_gate_tail_ms=500)
    speaker, pipeline_inst, _ = _speaker_with_mock_pipeline(monkeypatch, config)
    monkeypatch.setattr(speaker_mod.sd, "play", MagicMock())
    pipeline_inst.side_effect = lambda *a, **k: iter(
        [("g", "p", np.array([0.01], dtype=np.float32))]
    )
    perf_samples = [10.0, 10.05, 99.0]
    perf_calls: list[float] = []

    def fake_perf() -> float:
        perf_calls.append(1.0)
        return perf_samples[len(perf_calls) - 1]

    monkeypatch.setattr(speaker_mod.time, "perf_counter", fake_perf)
    tail_slept: list[float] = []
    monkeypatch.setattr(
        speaker_mod.time, "sleep", lambda s: tail_slept.append(s)
    )

    latency_ms = speaker.speak("ok")

    assert latency_ms == pytest.approx(50.0)
    assert len(perf_calls) == 2
    assert tail_slept == [0.5]
