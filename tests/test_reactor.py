import json
from unittest.mock import MagicMock

import numpy as np
import pytest

from heckler.config import HecklerConfig
from heckler.models import AudioChunk, CommentType, DiscardReason, ReactorResult, Utterance
from heckler.reactor import Reactor, completion_assistant_text

_TEST_SYSTEM_PROMPT = "You are a test reactor."
_TEST_EXAMPLES = [
    {"transcript": "test", "comment": "test reply", "score": 0.8, "type": "observation"}
]


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

    r = Reactor(reactor_cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
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

    r = Reactor(reactor_cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    result, _, discard = r.react(_audio_utt("works on my machine"), "")
    assert discard is None
    assert result is not None
    assert result.comment == "Ship it."


def test_invalid_json_returns_none(monkeypatch, reactor_cfg: HecklerConfig):
    mock_completion = MagicMock(
        return_value=_litellm_completion_response("completely invalid llm output")
    )
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(reactor_cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    result, latency, discard = r.react(_audio_utt("x"), "")
    assert result is None
    assert latency >= 0.0
    assert discard == DiscardReason.LLM_ERROR


def test_score_below_threshold_returns_none(monkeypatch):
    cfg = HecklerConfig(openai_api_key="k", score_threshold=0.65)
    payload = '{"comment": "Meh.", "score": 0.40, "type": "observation"}'
    mock_completion = MagicMock(return_value=_litellm_completion_response(payload))
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    result, _, discard = r.react(_audio_utt("speech"), "")
    assert result is None
    assert discard == DiscardReason.SCORE_GATE


def test_score_at_exact_threshold_passes(monkeypatch):
    cfg = HecklerConfig(openai_api_key="k", score_threshold=0.65)
    payload = '{"comment": "Edge.", "score": 0.65, "type": "callback"}'
    mock_completion = MagicMock(return_value=_litellm_completion_response(payload))
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    result, _, discard = r.react(_audio_utt("speech"), "")
    assert discard is None
    assert result is not None
    assert result.score == 0.65


def test_api_exception_returns_none_no_raise(monkeypatch, reactor_cfg: HecklerConfig):
    mock_completion = MagicMock(side_effect=ConnectionError("upstream"))
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(reactor_cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    result, latency, discard = r.react(_audio_utt("y"), "")
    assert result is None
    assert latency >= 0.0
    assert discard == DiscardReason.LLM_ERROR


def test_examples_json_types_are_comment_type_members():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    examples = json.loads(
        (root / "prompts" / "heckler" / "examples.json").read_text(encoding="utf-8")
    )
    assert examples, "prompts/heckler/examples.json must contain at least one example"
    for ex in examples:
        CommentType(ex["type"])  # raises if invalid


def test_invalid_comment_type_in_json_returns_unknown():
    raw = '{"comment": "x", "score": 0.9, "type": "not_a_real_type"}'
    r = Reactor.__new__(Reactor)
    result = Reactor._parse_response(r, raw)
    assert result is not None
    assert result.comment_type == CommentType.UNKNOWN


def test_react_unrecognized_type_string_returns_unknown_when_score_passes(monkeypatch):
    """Falsifier: full ``react`` path must surface UNKNOWN (not None) for unrecognized ``type``."""
    cfg = HecklerConfig(openai_api_key="k", score_threshold=0.65)
    payload = '{"comment": "ok", "score": 0.9, "type": "not_a_real_type"}'
    mock_completion = MagicMock(return_value=_litellm_completion_response(payload))
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    result, _, discard = r.react(_audio_utt("hi"), "")
    assert discard is None
    assert result is not None
    assert result.comment_type == CommentType.UNKNOWN
    assert result.comment == "ok"


def test_react_unrecognized_type_string_still_hits_score_gate(monkeypatch):
    """UNKNOWN fallback must not bypass the score threshold."""
    cfg = HecklerConfig(openai_api_key="k", score_threshold=0.65)
    payload = '{"comment": "low", "score": 0.40, "type": "bogus_type_xyz"}'
    mock_completion = MagicMock(return_value=_litellm_completion_response(payload))
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    result, _, discard = r.react(_audio_utt("x"), "")
    assert result is None
    assert discard == DiscardReason.SCORE_GATE


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

    r = Reactor(reactor_cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    result, _, discard = r.react(_audio_utt("x"), "")
    assert result is None
    assert discard == DiscardReason.LLM_ERROR


def test_react_none_completion_response_returns_llm_error(monkeypatch, reactor_cfg: HecklerConfig):
    """``litellm.completion`` returning ``None`` yields empty assistant text and LLM_ERROR (not raised)."""
    monkeypatch.setattr("litellm.completion", MagicMock(return_value=None))

    r = Reactor(reactor_cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    result, _, discard = r.react(_audio_utt("x"), "")
    assert result is None
    assert discard == DiscardReason.LLM_ERROR


def test_correlation_set_from_completion_response_ids(monkeypatch, reactor_cfg: HecklerConfig):
    """After success, thread-local correlation carries stable primitive completion fields."""
    from heckler.tracing_context import get_correlation

    payload = '{"comment": "Neat.", "score": 0.9, "type": "observation"}'
    resp = _litellm_completion_response(payload)
    resp.id = "chatcmpl-testid"
    resp.model = "openai/gpt-4o-mini"
    mock_completion = MagicMock(return_value=resp)
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(reactor_cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    r.react(_audio_utt("hello"), "")
    assert get_correlation() == {
        "completion_id": "chatcmpl-testid",
        "model": "openai/gpt-4o-mini",
    }


def test_litellm_completion_gets_metadata_when_hosted_observability_env(
    monkeypatch, reactor_cfg: HecklerConfig
):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    payload = '{"comment": "Neat.", "score": 0.9, "type": "observation"}'
    mock_completion = MagicMock(return_value=_litellm_completion_response(payload))
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(reactor_cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    r.react(_audio_utt("x"), "")
    kwargs = mock_completion.call_args.kwargs
    assert kwargs["metadata"]["generation_name"] == "heckler.react"
    assert "heckler-reactor" in kwargs["metadata"]["tags"]


def test_litellm_completion_has_no_metadata_without_observability_env(
    monkeypatch, reactor_cfg: HecklerConfig
):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    payload = '{"comment": "Neat.", "score": 0.9, "type": "observation"}'
    mock_completion = MagicMock(return_value=_litellm_completion_response(payload))
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(reactor_cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    r.react(_audio_utt("x"), "")
    kwargs = mock_completion.call_args.kwargs
    assert "metadata" not in kwargs


def test_magicmock_response_attrs_do_not_populate_correlation(monkeypatch, reactor_cfg: HecklerConfig):
    """Falsifier: default MagicMock placeholder attributes must not stringify into correlation rows."""
    from heckler.tracing_context import get_correlation

    payload = '{"comment": "Neat.", "score": 0.9, "type": "observation"}'
    resp = _litellm_completion_response(payload)
    mock_completion = MagicMock(return_value=resp)
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(reactor_cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    r.react(_audio_utt("x"), "")
    assert get_correlation() is None


def test_llm_exception_resets_correlation_thread_local(monkeypatch, reactor_cfg: HecklerConfig):
    from heckler.tracing_context import get_correlation, set_correlation

    set_correlation({"stale": "keep"})
    mock_completion = MagicMock(side_effect=ConnectionError("upstream"))
    monkeypatch.setattr("litellm.completion", mock_completion)

    r = Reactor(reactor_cfg, _TEST_SYSTEM_PROMPT, _TEST_EXAMPLES)
    r.react(_audio_utt("x"), "")
    assert get_correlation() is None
