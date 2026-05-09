from dataclasses import dataclass
import os
from typing import Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class HecklerConfig:
    sample_rate: int = 16_000
    capture_device: Optional[int] = None
    vad_threshold: float = 0.5
    min_speech_duration_ms: int = 500
    max_speech_duration_s: float = 15.0
    silence_duration_ms: int = 800
    whisper_model_size: str = "large-v3"
    whisper_compute_type: str = "int8_float16"
    whisper_beam_size: int = 3
    whisper_language: str = "en"
    density_threshold: float = 0.40
    min_word_count: int = 4
    context_window_size: int = 5
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_max_tokens: int = 150
    llm_temperature: float = 0.9
    score_threshold: float = 0.65
    score_override_threshold: float = 0.90
    anthropic_api_key: str = ""
    min_output_interval_s: float = 12.0
    kokoro_voice: str = "af_sarah"
    kokoro_speed: float = 1.05
    log_dir: str = "logs"
    log_density_failures: bool = False
    queue_maxsize: int = 10


def load_config() -> HecklerConfig:
    load_dotenv()
    return HecklerConfig(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        whisper_model_size=os.getenv("WHISPER_MODEL", "large-v3"),
        score_threshold=float(os.getenv("SCORE_THRESHOLD", "0.65")),
        min_output_interval_s=float(os.getenv("PACING_INTERVAL", "12.0")),
        kokoro_voice=os.getenv("KOKORO_VOICE", "af_sarah"),
        log_density_failures=os.getenv("LOG_DENSITY_FAILURES", "false").lower() == "true",
    )
