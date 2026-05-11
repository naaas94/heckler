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
    llm_model: str = "openai/gpt-4o-mini"
    llm_max_tokens: int = 150
    llm_temperature: float = 0.9
    score_threshold: float = 0.80
    score_override_threshold: float = 0.90
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ollama_api_base: str = ""
    min_output_interval_s: float = 12.0
    kokoro_voice: str = "af_sarah"
    kokoro_speed: float = 1.05
    sqlite_database_path: str = "logs/heckler.db"
    log_density_failures: bool = False
    queue_maxsize: int = 10


def load_config() -> HecklerConfig:
    load_dotenv()
    llm_env = (os.getenv("HECKLER_LLM_MODEL") or "").strip()
    llm_model = llm_env if llm_env else "openai/gpt-4o-mini"
    db_env = (os.getenv("HECKLER_DATABASE_PATH") or "").strip()
    sqlite_database_path = db_env if db_env else "logs/heckler.db"
    return HecklerConfig(
        llm_model=llm_model,
        sqlite_database_path=sqlite_database_path,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        ollama_api_base=os.getenv("OLLAMA_API_BASE", ""),
        whisper_model_size=os.getenv("WHISPER_MODEL", "large-v3"),
        score_threshold=float(os.getenv("SCORE_THRESHOLD", "0.80")),
        min_output_interval_s=float(os.getenv("PACING_INTERVAL", "12.0")),
        kokoro_voice=os.getenv("KOKORO_VOICE", "af_sarah"),
        log_density_failures=os.getenv("LOG_DENSITY_FAILURES", "false").lower() == "true",
    )
