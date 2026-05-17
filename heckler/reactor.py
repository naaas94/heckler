from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Optional

from heckler.config import HecklerConfig
from heckler.models import CommentType, DiscardReason, ReactorResult, Utterance
from heckler.tracing_context import clear_correlation, set_correlation

logger = logging.getLogger(__name__)

_JSON_OBJECT_RE = re.compile(r"\{[^}]+\}")


def completion_assistant_text(response: Any) -> str:
    """
    Extract assistant message text from a ``litellm.completion`` (OpenAI-compatible) response.

    Expected shape: ``choices[0].message.content`` as ``str`` or a list of content parts.
    Documented for downstream regression tests (LiteLLM / provider response drift).
    """
    if response is None:
        return ""
    choices = getattr(response, "choices", None)
    if not choices:
        return ""
    choice0 = choices[0]
    msg = getattr(choice0, "message", None)
    if msg is None:
        return ""
    content = getattr(msg, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    chunks.append(str(block.get("text", "")))
            else:
                text_attr = getattr(block, "text", None)
                if text_attr is not None:
                    chunks.append(str(text_attr))
        return "".join(chunks)
    return str(content)


def _scalar_string_for_correlation(val: Any) -> Optional[str]:
    """Accept only JSON-safe primitives for correlation; skip MagicMock / nested objects."""
    if val is None:
        return None
    if isinstance(val, bool):
        return str(val).lower()
    if isinstance(val, (str, int, float)):
        return str(val)
    return None


def _correlation_from_completion_response(response: Any) -> Optional[dict[str, str]]:
    """Map LiteLLM/OpenAI-shaped completion objects to flat string metadata for SQLite."""
    if response is None:
        return None
    out: dict[str, str] = {}
    ident = _scalar_string_for_correlation(getattr(response, "id", None))
    if ident:
        out["completion_id"] = ident
    model = _scalar_string_for_correlation(getattr(response, "model", None))
    if model:
        out["model"] = model
    fp = _scalar_string_for_correlation(getattr(response, "system_fingerprint", None))
    if fp:
        out["system_fingerprint"] = fp
    hidden = getattr(response, "_hidden_params", None)
    if isinstance(hidden, dict):
        for src_key, dest_key in (
            ("litellm_call_id", "litellm_call_id"),
            ("model_id", "litellm_model_id"),
        ):
            s = _scalar_string_for_correlation(hidden.get(src_key))
            if s:
                out[dest_key] = s
    return out or None


def _hosted_observability_env_active() -> bool:
    """
    True when common Langfuse / LangSmith env wiring is present so LiteLLM can tag generations.

    Does not import optional SDKs or mutate global LiteLLM callback lists (no duplicate roots).
    """
    if os.getenv("LANGFUSE_PUBLIC_KEY", "").strip() and os.getenv(
        "LANGFUSE_SECRET_KEY", ""
    ).strip():
        return True
    tracing_on = os.getenv("LANGCHAIN_TRACING_V2", "").strip().lower() in (
        "true",
        "1",
    ) or os.getenv("LANGSMITH_TRACING", "").strip().lower() in ("true", "1")
    if tracing_on and (
        os.getenv("LANGCHAIN_API_KEY", "").strip()
        or os.getenv("LANGSMITH_API_KEY", "").strip()
    ):
        return True
    return False


def _litellm_observability_completion_kwargs() -> dict[str, Any]:
    """
    Extra kwargs for ``litellm.completion`` when hosted tracing env is enabled.

    LiteLLM forwards ``metadata`` to its logging/callback pipeline (Langfuse/Langsmith-style
    tooling reads keys like ``generation_name`` when callbacks are configured via env/package).
    """
    if not _hosted_observability_env_active():
        return {}
    return {
        "metadata": {
            "tags": ["heckler", "heckler-reactor"],
            "generation_name": "heckler.react",
        }
    }


def _litellm_auth_params(config: HecklerConfig) -> dict[str, Any]:
    """Map ``HecklerConfig`` keys to LiteLLM kwargs; omit keys when empty (env defaults)."""
    model = (config.llm_model or "").strip()
    if not model:
        return {}
    provider, _, _ = model.partition("/")
    provider = provider.lower()
    if provider in ("openai", "azure"):
        if config.openai_api_key:
            return {"api_key": config.openai_api_key}
        return {}
    if provider == "anthropic":
        if config.anthropic_api_key:
            return {"api_key": config.anthropic_api_key}
        return {}
    if provider == "ollama":
        if config.ollama_api_base:
            return {"api_base": config.ollama_api_base}
        return {}
    # Bare model id (no ``provider/`` prefix): LiteLLM infers routing; prefer explicit OpenAI key.
    if "/" not in model and config.openai_api_key:
        return {"api_key": config.openai_api_key}
    return {}


class Reactor:
    """LiteLLM-backed commentary generation with JSON parsing and score gating."""

    def __init__(
        self,
        config: HecklerConfig,
        system_prompt: str,
        examples: list[dict[str, Any]],
    ) -> None:
        """
        ``system_prompt`` and ``examples`` are caller-resolved persona content (no filesystem I/O).
        Pre-renders examples_block string (static, no per-call overhead).
        """
        self._config = config
        self._system_prompt = system_prompt
        self._examples_block = _format_examples_block(examples)

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
        import litellm

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
        extra = _litellm_auth_params(self._config)
        observe_kw = _litellm_observability_completion_kwargs()
        clear_correlation()
        try:
            response = litellm.completion(
                model=self._config.llm_model,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=self._config.llm_max_tokens,
                temperature=self._config.llm_temperature,
                **extra,
                **observe_kw,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            logger.error("LLM API call failed: %s", exc)
            clear_correlation()
            return None, elapsed_ms, DiscardReason.LLM_ERROR

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        corr = _correlation_from_completion_response(response)
        if corr:
            set_correlation(corr)
        else:
            clear_correlation()
        raw_text = completion_assistant_text(response)
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
            logger.warning(
                "LLM JSON unrecognized CommentType %r, falling back to UNKNOWN: %r",
                type_val,
                raw,
            )
            ct = CommentType.UNKNOWN

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
