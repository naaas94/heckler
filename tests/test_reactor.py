import json
from unittest.mock import MagicMock

import numpy as np
import pytest

from heckler.config import HecklerConfig
from heckler.models import AudioChunk, CommentType, DiscardReason, ReactorResult, Utterance
from heckler.reactor import Reactor


def _audio_utt(transcript: str) -> Utterance:
    chunk = AudioChunk(audio=np.zeros(8, dtype=np.float32), captured_at=0.0)
    return Utterance(
        utterance_id="id-1",
        transcript=transcript,
        semantic_density=0.5,
        transcribed_at=1.0,
        audio_chunk=chunk,
    )


def _text_message(body: str) -> MagicMock:
    msg = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = body
    msg.content = [block]
    return msg


@pytest.fixture
def reactor_cfg() -> HecklerConfig:
    return HecklerConfig(anthropic_api_key="sk-test-key", score_threshold=0.65)


def test_valid_json_returns_reactor_result(monkeypatch, reactor_cfg: HecklerConfig):
    payload = '{"comment": "Neat.", "score": 0.9, "type": "observation"}'
    mock_create = MagicMock(return_value=_text_message(payload))
    mock_client = MagicMock()
    mock_client.messages.create = mock_create
    monkeypatch.setattr("heckler.reactor.Anthropic", lambda **_: mock_client)

    r = Reactor(reactor_cfg)
    utt = _audio_utt("hello there")
    result, latency, discard = r.react(utt, context_block="(none)")
    assert mock_create.called
    assert isinstance(latency, float)
    assert discard is None
    assert result is not None
    assert result.comment == "Neat."
    assert result.score == 0.9
    assert result.comment_type == CommentType.OBSERVATION
    assert result.raw_response == payload


def test_leading_text_before_json_regex_fallback(monkeypatch, reactor_cfg: HecklerConfig):
    raw = (
        'Thought: sure thing {"comment": "Ship it.", "score": 0.88, "type": "sarcasm"}'
    )
    mock_create = MagicMock(return_value=_text_message(raw))
    mock_client = MagicMock()
    mock_client.messages.create = mock_create
    monkeypatch.setattr("heckler.reactor.Anthropic", lambda **_: mock_client)

    r = Reactor(reactor_cfg)
    result, _, discard = r.react(_audio_utt("works on my machine"), "")
    assert discard is None
    assert result is not None
    assert result.comment == "Ship it."


def test_invalid_json_returns_none(monkeypatch, reactor_cfg: HecklerConfig):
    mock_create = MagicMock(return_value=_text_message("completely invalid llm output"))
    mock_client = MagicMock()
    mock_client.messages.create = mock_create
    monkeypatch.setattr("heckler.reactor.Anthropic", lambda **_: mock_client)

    r = Reactor(reactor_cfg)
    result, latency, discard = r.react(_audio_utt("x"), "")
    assert result is None
    assert latency >= 0.0
    assert discard == DiscardReason.LLM_ERROR


def test_score_below_threshold_returns_none(monkeypatch):
    cfg = HecklerConfig(anthropic_api_key="k", score_threshold=0.65)
    payload = '{"comment": "Meh.", "score": 0.40, "type": "observation"}'
    mock_create = MagicMock(return_value=_text_message(payload))
    mock_client = MagicMock()
    mock_client.messages.create = mock_create
    monkeypatch.setattr("heckler.reactor.Anthropic", lambda **_: mock_client)

    r = Reactor(cfg)
    result, _, discard = r.react(_audio_utt("speech"), "")
    assert result is None
    assert discard == DiscardReason.SCORE_GATE


def test_score_at_exact_threshold_passes(monkeypatch):
    cfg = HecklerConfig(anthropic_api_key="k", score_threshold=0.65)
    payload = '{"comment": "Edge.", "score": 0.65, "type": "callback"}'
    mock_create = MagicMock(return_value=_text_message(payload))
    mock_client = MagicMock()
    mock_client.messages.create = mock_create
    monkeypatch.setattr("heckler.reactor.Anthropic", lambda **_: mock_client)

    r = Reactor(cfg)
    result, _, discard = r.react(_audio_utt("speech"), "")
    assert discard is None
    assert result is not None
    assert result.score == 0.65


def test_api_exception_returns_none_no_raise(monkeypatch, reactor_cfg: HecklerConfig):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = ConnectionError("upstream")
    monkeypatch.setattr("heckler.reactor.Anthropic", lambda **_: mock_client)

    r = Reactor(reactor_cfg)
    result, latency, discard = r.react(_audio_utt("y"), "")
    assert result is None
    assert latency >= 0.0
    assert discard == DiscardReason.LLM_ERROR


def test_examples_json_types_are_comment_type_members():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    examples = json.loads((root / "prompts" / "examples.json").read_text(encoding="utf-8"))
    for ex in examples:
        CommentType(ex["type"])  # raises if invalid


def test_invalid_comment_type_in_json_returns_none():
    raw = '{"comment": "x", "score": 0.9, "type": "not_a_real_type"}'
    r = Reactor.__new__(Reactor)
    assert Reactor._parse_response(r, raw) is None


def test_parse_response_regex_used_when_direct_json_fails():
    """If regex fallback were removed, preamble-wrapped JSON would fail to parse."""
    raw = 'noise {"comment": "ok", "score": 0.8, "type": "absurdist"}'
    r = Reactor.__new__(Reactor)
    out = Reactor._parse_response(r, raw)
    assert out is not None
    assert out.comment == "ok"


def test_parse_full_round_trip_reactor_result_fields():
    raw = '{"comment": "a", "score": 1.0, "type": "sarcasm"}'
    r = Reactor.__new__(Reactor)
    out = Reactor._parse_response(r, raw)
    assert isinstance(out, ReactorResult)
    assert out.raw_response == raw
