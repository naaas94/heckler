from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

from anthropic import Anthropic

from heckler.config import HecklerConfig
from heckler.models import CommentType, DiscardReason, ReactorResult, Utterance

logger = logging.getLogger(__name__)

_JSON_OBJECT_RE = re.compile(r"\{[^}]+\}")


class Reactor:
    """Anthropic-backed commentary generation with JSON parsing and score gating."""

    def __init__(self, config: HecklerConfig) -> None:
        """
        Loads system prompt from prompts/system.md.
        Loads examples from prompts/examples.json.
        Initializes Anthropic client.
        Pre-renders examples_block string (static, no per-call overhead).
        """
        self._config = config
        root = Path(__file__).resolve().parent.parent
        self._system_prompt = (root / "prompts" / "system.md").read_text(encoding="utf-8")
        examples_path = root / "prompts" / "examples.json"
        raw_examples: list[dict[str, Any]] = json.loads(
            examples_path.read_text(encoding="utf-8")
        )
        self._examples_block = _format_examples_block(raw_examples)
        self._client = Anthropic(api_key=config.anthropic_api_key)

    def react(
        self,
        utterance: Utterance,
        context_block: str,
    ) -> tuple[Optional[ReactorResult], float, Optional[DiscardReason]]:
        """
        Returns (result_or_none, llm_latency_ms, discard_reason_or_none).

        On success: (result, latency_ms, None).

        result is None with a non-None discard_reason if:
          - API call fails (log error, do not raise) → DiscardReason.LLM_ERROR
          - Response is not parseable JSON (log raw response) → DiscardReason.LLM_ERROR
          - score < config.score_threshold (score gate applied HERE) → DiscardReason.SCORE_GATE

        On parse failure: attempt regex fallback to extract JSON object.
        score gate: if result.score < config.score_threshold, return None with SCORE_GATE.
        """
        n_ctx = self._config.context_window_size
        user_content = (
            "Examples of the register and quality bar:\n\n"
            f"{self._examples_block}\n\n"
            "---\n\n"
            f"Recent context (last {n_ctx} utterances):\n"
            f"{context_block}\n\n"
            "Current utterance to react to:\n"
            f'"{utterance.transcript}"\n\n'
            "Respond with JSON only."
        )
        t0 = time.perf_counter()
        raw_text: str
        try:
            message = self._client.messages.create(
                model=self._config.llm_model,
                max_tokens=self._config.llm_max_tokens,
                temperature=self._config.llm_temperature,
                system=self._system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            logger.error("Anthropic API call failed: %s", exc)
            return None, elapsed_ms, DiscardReason.LLM_ERROR

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        raw_text = _extract_text_content(message)
        parsed = self._parse_response(raw_text)
        if parsed is None:
            return None, elapsed_ms, DiscardReason.LLM_ERROR
        if parsed.score < self._config.score_threshold:
            return None, elapsed_ms, DiscardReason.SCORE_GATE
        return parsed, elapsed_ms, None

    def _parse_response(self, raw: str) -> Optional[ReactorResult]:
        r"""
        1. Try json.loads(raw) directly.
        2. On failure, try regex: r'\{[^}]+\}' to extract first JSON object.
        3. On failure, return None and log raw string.
        Validates: comment is str, score is float in [0,1], type is valid CommentType.
        """
        text = raw.strip()
        data: Optional[dict[str, Any]] = None
        try:
            loaded = json.loads(text)
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError:
            pass

        if data is None:
            match = _JSON_OBJECT_RE.search(text)
            if match is not None:
                try:
                    loaded = json.loads(match.group(0))
                    if isinstance(loaded, dict):
                        data = loaded
                except json.JSONDecodeError:
                    pass

        if data is None:
            logger.warning("Could not parse JSON from LLM response: %r", raw)
            return None

        try:
            comment = data["comment"]
            score_val = data["score"]
            type_val = data["type"]
        except (KeyError, TypeError):
            logger.warning("LLM JSON missing required keys: %r", raw)
            return None

        if not isinstance(comment, str):
            logger.warning("LLM JSON comment must be str: %r", raw)
            return None
        if not isinstance(score_val, (int, float)):
            logger.warning("LLM JSON score must be numeric: %r", raw)
            return None
        score = float(score_val)
        if not 0.0 <= score <= 1.0:
            logger.warning("LLM JSON score out of range [0,1]: %r", raw)
            return None
        if not isinstance(type_val, str):
            logger.warning("LLM JSON type must be str: %r", raw)
            return None
        try:
            ct = CommentType(type_val)
        except ValueError:
            logger.warning("LLM JSON invalid CommentType %r: %r", type_val, raw)
            return None

        return ReactorResult(
            comment=comment,
            score=score,
            comment_type=ct,
            raw_response=raw,
        )


def _format_examples_block(examples: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for ex in examples:
        resp_obj = {
            "comment": ex["comment"],
            "score": ex["score"],
            "type": ex["type"],
        }
        parts.append(
            f'Input: "{ex["transcript"]}"\n'
            f"Response: {json.dumps(resp_obj)}"
        )
    return "\n\n".join(parts)


def _extract_text_content(message: Any) -> str:
    """Concatenate text blocks from an Anthropic message response."""
    chunks: list[str] = []
    for block in message.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            chunks.append(getattr(block, "text", ""))
        elif isinstance(block, dict) and block.get("type") == "text":
            chunks.append(str(block.get("text", "")))
    return "".join(chunks)
