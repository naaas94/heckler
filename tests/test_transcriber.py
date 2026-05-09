import logging
import queue
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from heckler.config import HecklerConfig
from heckler.models import AudioChunk
from heckler import transcriber as transcriber_mod
from heckler.transcriber import Transcriber


@pytest.fixture
def config() -> HecklerConfig:
    return HecklerConfig()


def test_init_loads_model_and_logs_loading(config: HecklerConfig, caplog) -> None:
    with patch.object(transcriber_mod, "WhisperModel") as mock_wm:
        caplog.set_level(logging.INFO, logger="heckler.transcriber")
        Transcriber(config)
    mock_wm.assert_called_once_with(
        config.whisper_model_size,
        device="cuda",
        compute_type=config.whisper_compute_type,
    )
    assert "loading transcription model" in caplog.text.lower()


def test_transcribe_passes_required_kwargs(config: HecklerConfig) -> None:
    mock_model = MagicMock()
    seg = MagicMock()
    seg.text = "hello"
    mock_model.transcribe.return_value = ([seg], MagicMock())
    with patch.object(transcriber_mod, "WhisperModel", return_value=mock_model):
        tr = Transcriber(config)
    audio = np.zeros(320, dtype=np.float32)
    chunk = AudioChunk(audio=audio, captured_at=0.0)
    out = tr.transcribe(chunk)
    assert out == "hello"
    mock_model.transcribe.assert_called_once()
    kwargs = mock_model.transcribe.call_args.kwargs
    assert kwargs["vad_filter"] is True
    assert kwargs["condition_on_previous_text"] is False
    assert kwargs["word_timestamps"] is False
    assert kwargs["beam_size"] == config.whisper_beam_size
    assert kwargs["language"] == config.whisper_language


def test_transcribe_empty_segments_returns_empty_string(config: HecklerConfig) -> None:
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock())
    with patch.object(transcriber_mod, "WhisperModel", return_value=mock_model):
        tr = Transcriber(config)
    chunk = AudioChunk(audio=np.zeros(100, dtype=np.float32), captured_at=1.0)
    assert tr.transcribe(chunk) == ""


def test_run_forwards_empty_transcript(config: HecklerConfig) -> None:
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock())
    with patch.object(transcriber_mod, "WhisperModel", return_value=mock_model):
        tr = Transcriber(config)
    in_q: queue.Queue = queue.Queue()
    out_q: queue.Queue = queue.Queue()
    chunk = AudioChunk(audio=np.zeros(160, dtype=np.float32), captured_at=0.0)
    in_q.put(chunk)
    in_q.put(None)
    tr.run(in_q, out_q)
    uid, text = out_q.get_nowait()
    assert text == ""
    assert len(uid) == 36


def test_run_accepts_explicit_utterance_id(config: HecklerConfig) -> None:
    mock_model = MagicMock()
    seg = MagicMock()
    seg.text = "hi"
    mock_model.transcribe.return_value = ([seg], MagicMock())
    with patch.object(transcriber_mod, "WhisperModel", return_value=mock_model):
        tr = Transcriber(config)
    in_q: queue.Queue = queue.Queue()
    out_q: queue.Queue = queue.Queue()
    chunk = AudioChunk(audio=np.zeros(160, dtype=np.float32), captured_at=0.0)
    in_q.put(("fixed-id", chunk))
    in_q.put(None)
    tr.run(in_q, out_q)
    uid, text = out_q.get_nowait()
    assert uid == "fixed-id"
    assert text == "hi"


def test_init_failure_logs_and_reraises(config: HecklerConfig, caplog) -> None:
    caplog.set_level(logging.ERROR, logger="heckler.transcriber")
    with (
        patch.object(
            transcriber_mod,
            "WhisperModel",
            side_effect=RuntimeError("cuda unavailable"),
        ),
        pytest.raises(RuntimeError, match="cuda unavailable"),
    ):
        Transcriber(config)
    assert "failed to load transcription model" in caplog.text.lower()
