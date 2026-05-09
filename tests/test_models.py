import json

import numpy as np
import pytest

from heckler.config import HecklerConfig, load_config
from heckler.models import (
    AudioChunk,
    CommentType,
    DiscardReason,
    HeckleEvent,
    ReactorResult,
    Utterance,
    heckle_event_from_json_dict,
    heckle_event_json_round_trip,
    serialize_heckle_event,
    _json_safe_value,
)


def test_comment_type_enum_values():
    assert CommentType.SARCASM.value == "sarcasm"
    assert CommentType["PASSIVE_AGGRESSIVE"].value == "passive_aggressive"


def test_discard_reason_enum_values():
    assert DiscardReason.DENSITY_GATE.value == "density_gate"
    assert DiscardReason.LLM_ERROR.value == "llm_error"


def test_audio_chunk_and_utterance_construction():
    audio = np.zeros(1600, dtype=np.float32)
    chunk = AudioChunk(audio=audio, captured_at=123.45)
    utt = Utterance(
        utterance_id="u1",
        transcript="hello world",
        semantic_density=0.5,
        transcribed_at=456.0,
        audio_chunk=chunk,
    )
    assert utt.audio_chunk.audio.shape == (1600,)
    assert utt.audio_chunk.audio.dtype == np.float32


def test_heckle_event_serialization_round_trip_and_enums():
    event = HeckleEvent(
        utterance_id="abc",
        timestamp_iso="2026-05-08T12:00:00+00:00",
        transcript="test",
        semantic_density=0.42,
        passed_density_gate=True,
        reactor_result=ReactorResult(
            comment="nice",
            score=0.8,
            comment_type=CommentType.SARCASM,
            raw_response='{"comment":"nice"}',
        ),
        passed_score_gate=True,
        passed_pacing_gate=False,
        spoken=False,
        discard_reason=DiscardReason.PACING_GATE,
        cooldown_remaining_at_eval=3.0,
        llm_latency_ms=100.0,
        tts_latency_ms=None,
    )
    restored = heckle_event_json_round_trip(event)
    assert restored == event

    payload = serialize_heckle_event(event)
    text = json.dumps(payload)
    assert "audio_chunk" not in text
    assert '"comment_type": "sarcasm"' in text
    assert '"discard_reason": "pacing_gate"' in text


def test_serialize_strips_nested_audio_chunk_keys():
    nested = {"nested": {"audio_chunk": [1, 2], "keep": True}}
    cleaned = _json_safe_value(nested)
    assert "audio_chunk" not in json.dumps(cleaned)
    assert cleaned["nested"]["keep"] is True


def test_heckle_event_dict_missing_field_raises():
    bad = {"utterance_id": "x"}
    with pytest.raises(KeyError):
        heckle_event_from_json_dict(bad)


def test_heckler_config_defaults():
    cfg = HecklerConfig()
    assert cfg.sample_rate == 16_000
    assert cfg.capture_device is None
    assert cfg.whisper_model_size == "large-v3"
    assert cfg.score_threshold == 0.65
    assert cfg.log_density_failures is False


def test_load_config_requires_anthropic_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(KeyError):
        load_config()


def test_load_config_env_overrides(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("WHISPER_MODEL", "tiny")
    monkeypatch.setenv("SCORE_THRESHOLD", "0.7")
    monkeypatch.setenv("PACING_INTERVAL", "20")
    monkeypatch.setenv("KOKORO_VOICE", "af_bella")
    monkeypatch.setenv("LOG_DENSITY_FAILURES", "true")
    cfg = load_config()
    assert cfg.anthropic_api_key == "sk-test"
    assert cfg.whisper_model_size == "tiny"
    assert cfg.score_threshold == 0.7
    assert cfg.min_output_interval_s == 20.0
    assert cfg.kokoro_voice == "af_bella"
    assert cfg.log_density_failures is True
    assert cfg.sample_rate == 16_000
