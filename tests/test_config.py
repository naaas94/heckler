import dataclasses

import pytest

from heckler.config import HecklerConfig, load_config


def test_heckler_config_tts_gate_tail_ms_default() -> None:
    cfg = HecklerConfig()
    assert cfg.tts_gate_tail_ms == 400


def test_load_config_tts_gate_tail_ms_env_override(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TTS_GATE_TAIL_MS", "300")
    cfg = load_config()
    assert cfg.tts_gate_tail_ms == 300


def test_load_config_tts_gate_tail_ms_zero_disables_tail(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TTS_GATE_TAIL_MS", "0")
    cfg = load_config()
    assert cfg.tts_gate_tail_ms == 0


def test_load_config_tts_gate_tail_ms_invalid_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TTS_GATE_TAIL_MS", "not-a-number")
    with pytest.raises(ValueError):
        load_config()


def test_heckler_config_transcribe_field_defaults() -> None:
    cfg = HecklerConfig()
    assert cfg.mode == "persona"
    assert cfg.transcribe_max_speech_duration_s == 45.0
    assert cfg.transcribe_silence_duration_ms == 1500
    assert cfg.transcribe_min_speech_duration_ms == 250
    assert cfg.transcripts_dir == "transcripts"
    assert cfg.session_name is None


def test_load_config_transcribe_env_overrides(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HECKLER_MODE", "  transcribe  ")
    monkeypatch.setenv("HECKLER_SESSION_NAME", "  my-session  ")
    monkeypatch.setenv("HECKLER_TRANSCRIPTS_DIR", "  /var/out  ")
    cfg = load_config()
    assert cfg.mode == "transcribe"
    assert cfg.session_name == "my-session"
    assert cfg.transcripts_dir == "/var/out"


def test_load_config_session_name_empty_string_is_none(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HECKLER_SESSION_NAME", "   ")
    cfg = load_config()
    assert cfg.session_name is None


def test_load_config_transcripts_dir_whitespace_falls_back(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HECKLER_TRANSCRIPTS_DIR", "   ")
    cfg = load_config()
    assert cfg.transcripts_dir == "transcripts"


def test_load_config_mode_whitespace_falls_back_to_persona(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HECKLER_MODE", "   ")
    cfg = load_config()
    assert cfg.mode == "persona"


def test_heckler_config_partial_kwarg_construction_unchanged() -> None:
    cfg = HecklerConfig(anthropic_api_key="test-key")
    assert cfg.anthropic_api_key == "test-key"
    assert cfg.mode == "persona"
    assert cfg.session_name is None


def test_heckler_config_frozen_blocks_assignment() -> None:
    cfg = HecklerConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.mode = "transcribe"  # type: ignore[misc]


def test_replace_updates_mode_without_touching_transcribe_defaults() -> None:
    """Falsifier for T4-style ``replace`` on frozen config (VAD override wiring)."""
    base = HecklerConfig()
    updated = dataclasses.replace(base, mode="transcribe", session_name="s1")
    assert updated.mode == "transcribe"
    assert updated.session_name == "s1"
    assert updated.transcribe_max_speech_duration_s == 45.0
    assert updated.transcribe_silence_duration_ms == 1500
    assert updated.transcribe_min_speech_duration_ms == 250
