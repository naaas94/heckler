import json
from unittest.mock import MagicMock

import numpy as np
import pytest

from heckler.config import HecklerConfig
from heckler.models import AudioChunk, CommentType, DiscardReason, ReactorResult, Utterance
from heckler.reactor import Reactor, completion_assistant_text


def _audio_utt(transcript: str) -> Utterance:
    chunk = AudioChunk(audio=np.zeros(8, dtype=np.float32), captured_at=0.0)
    return Utterance(
        utterance_id="id-1",
        transcript=transcript,
        semantic_density=0.5,
        transcribed_at=1.0,
        audio_chunk=chunk,
    )


def _litellm_completion_response(body: str) -> MagicMock:
    """OpenAI-shaped object compatible with ``completion_assistant_text``."""
    resp = MagicMock()
    message = MagicMock()
    message.content = body
    choice = MagicMock()
    choice.message = message
    resp.choices = [choice]
    return resp


@pytest.fixture
def reactor_cfg() -> HecklerConfig:
    return HecklerConfig(openai_api_key="sk-test-key", score_threshold=0.65)


def test_valid_json_returns_reactor_result(monkeypatch, reactor_cfg: HecklerConfig):
    payload = '{"comment": "Neat.", "score": 0.9, "type": "observation"}'
    mock_completion = MagicMock(return_value=_litellm_completion_response(payload))
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(reactor_cfg)
    utt = _audio_utt("hello there")
    result, latency, discard = r.react(utt, context_block="(none)")
    assert mock_completion.called
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
    mock_completion = MagicMock(return_value=_litellm_completion_response(raw))
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(reactor_cfg)
    result, _, discard = r.react(_audio_utt("works on my machine"), "")
    assert discard is None
    assert result is not None
    assert result.comment == "Ship it."


def test_invalid_json_returns_none(monkeypatch, reactor_cfg: HecklerConfig):
    mock_completion = MagicMock(
        return_value=_litellm_completion_response("completely invalid llm output")
    )
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(reactor_cfg)
    result, latency, discard = r.react(_audio_utt("x"), "")
    assert result is None
    assert latency >= 0.0
    assert discard == DiscardReason.LLM_ERROR


def test_score_below_threshold_returns_none(monkeypatch):
    cfg = HecklerConfig(openai_api_key="k", score_threshold=0.65)
    payload = '{"comment": "Meh.", "score": 0.40, "type": "observation"}'
    mock_completion = MagicMock(return_value=_litellm_completion_response(payload))
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(cfg)
    result, _, discard = r.react(_audio_utt("speech"), "")
    assert result is None
    assert discard == DiscardReason.SCORE_GATE


def test_score_at_exact_threshold_passes(monkeypatch):
    cfg = HecklerConfig(openai_api_key="k", score_threshold=0.65)
    payload = '{"comment": "Edge.", "score": 0.65, "type": "callback"}'
    mock_completion = MagicMock(return_value=_litellm_completion_response(payload))
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(cfg)
    result, _, discard = r.react(_audio_utt("speech"), "")
    assert discard is None
    assert result is not None
    assert result.score == 0.65


def test_api_exception_returns_none_no_raise(monkeypatch, reactor_cfg: HecklerConfig):
    mock_completion = MagicMock(side_effect=ConnectionError("upstream"))
    monkeypatch.setattr("litellm.completion", mock_completion)

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


def test_completion_assistant_text_joins_list_text_parts():
    """Regression: multimodal-style ``content`` lists must stringify without dropping JSON."""
    resp = MagicMock()
    msg = MagicMock()
    msg.content = [{"type": "text", "text": '{"comment": "hi", "score": 0.9, "type": "observation"}'}]
    choice = MagicMock()
    choice.message = msg
    resp.choices = [choice]
    assert (
        completion_assistant_text(resp)
        == '{"comment": "hi", "score": 0.9, "type": "observation"}'
    )


def test_completion_assistant_text_plain_string_at_choices_zero_message_content():
    """Flag 3 / T11: LiteLLM/OpenAI-shaped responses expose assistant text as ``str`` on ``choices[0].message.content``."""
    plain = '{"comment": "flag3", "score": 0.9, "type": "observation"}'
    resp = MagicMock()
    msg = MagicMock()
    msg.content = plain
    choice0 = MagicMock()
    choice0.message = msg
    resp.choices = [choice0]
    assert completion_assistant_text(resp) == plain


def test_react_empty_choices_returns_llm_error(monkeypatch, reactor_cfg: HecklerConfig):
    """Malformed completion shape: no choices → empty extracted text → parse failure."""
    resp = MagicMock()
    resp.choices = []
    monkeypatch.setattr("litellm.completion", MagicMock(return_value=resp))

    r = Reactor(reactor_cfg)
    result, _, discard = r.react(_audio_utt("x"), "")
    assert result is None
    assert discard == DiscardReason.LLM_ERROR


def test_react_none_completion_response_returns_llm_error(monkeypatch, reactor_cfg: HecklerConfig):
    """``litellm.completion`` returning ``None`` yields empty assistant text and LLM_ERROR (not raised)."""
    monkeypatch.setattr("litellm.completion", MagicMock(return_value=None))

    r = Reactor(reactor_cfg)
    result, _, discard = r.react(_audio_utt("x"), "")
    assert result is None
    assert discard == DiscardReason.LLM_ERROR
