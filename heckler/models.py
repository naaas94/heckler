from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional, cast

import numpy as np


class CommentType(str, Enum):
    SARCASM = "sarcasm"
    DEFLATION = "deflation"
    CALLBACK = "callback"
    OBSERVATION = "observation"
    ABSURDIST = "absurdist"
    PASSIVE_AGGRESSIVE = "passive_aggressive"
    UNKNOWN = "unknown"


class DiscardReason(str, Enum):
    DENSITY_GATE = "density_gate"
    SCORE_GATE = "score_gate"
    PACING_GATE = "pacing_gate"
    LLM_ERROR = "llm_error"
    TTS_ERROR = "tts_error"


@dataclass
class AudioChunk:
    audio: np.ndarray  # float32, shape (N,), sample_rate=16000
    captured_at: float  # time.time() at capture boundary


@dataclass
class Utterance:
    utterance_id: str  # uuid4
    transcript: str
    semantic_density: float
    transcribed_at: float  # time.time()
    audio_chunk: AudioChunk  # kept for potential future use / debug


@dataclass
class ReactorResult:
    comment: str
    score: float  # 0.0–1.0, LLM self-assessed
    comment_type: CommentType
    raw_response: str  # verbatim LLM output, for logging


@dataclass
class HeckleEvent:
    utterance_id: str
    timestamp_iso: str  # ISO 8601
    transcript: str
    semantic_density: float
    passed_density_gate: bool
    reactor_result: Optional[ReactorResult]  # None if LLM errored
    passed_score_gate: Optional[bool]  # None if LLM errored
    passed_pacing_gate: Optional[bool]  # None if score_gate failed
    spoken: bool
    discard_reason: Optional[DiscardReason]
    cooldown_remaining_at_eval: Optional[float]
    llm_latency_ms: Optional[float]
    tts_latency_ms: Optional[float]


def _json_safe_value(obj: Any) -> Any:
    """Recursively coerce enums and containers for JSON; strip ``audio_chunk`` keys."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {
            k: _json_safe_value(v)
            for k, v in obj.items()
            if k != "audio_chunk"
        }
    if isinstance(obj, (list, tuple)):
        return [_json_safe_value(x) for x in obj]
    return obj


def serialize_heckle_event(event: HeckleEvent) -> dict[str, Any]:
    """JSON-serializable dict: enum values as strings, no ``audio_chunk`` keys."""
    raw = cast(dict[str, Any], asdict(event))
    return _json_safe_value(raw)


def heckle_event_from_json_dict(d: dict[str, Any]) -> HeckleEvent:
    """Reconstruct a ``HeckleEvent`` from JSON-compatible dict (e.g. after ``json.loads``)."""
    rr_raw = d.get("reactor_result")
    reactor_result: Optional[ReactorResult] = None
    if rr_raw is not None:
        reactor_result = ReactorResult(
            comment=rr_raw["comment"],
            score=rr_raw["score"],
            comment_type=CommentType(rr_raw["comment_type"]),
            raw_response=rr_raw["raw_response"],
        )
    dr = d.get("discard_reason")
    discard_reason: Optional[DiscardReason] = None
    if dr is not None:
        discard_reason = DiscardReason(dr)
    return HeckleEvent(
        utterance_id=d["utterance_id"],
        timestamp_iso=d["timestamp_iso"],
        transcript=d["transcript"],
        semantic_density=d["semantic_density"],
        passed_density_gate=d["passed_density_gate"],
        reactor_result=reactor_result,
        passed_score_gate=d["passed_score_gate"],
        passed_pacing_gate=d["passed_pacing_gate"],
        spoken=d["spoken"],
        discard_reason=discard_reason,
        cooldown_remaining_at_eval=d["cooldown_remaining_at_eval"],
        llm_latency_ms=d["llm_latency_ms"],
        tts_latency_ms=d["tts_latency_ms"],
    )


def heckle_event_json_round_trip(event: HeckleEvent) -> HeckleEvent:
    """Serialize to JSON and back; validates enum string coercion and schema."""
    payload = serialize_heckle_event(event)
    text = json.dumps(payload)
    back = json.loads(text)
    return heckle_event_from_json_dict(back)
