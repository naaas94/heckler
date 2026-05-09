"""TTS playback: Kokoro synthesis, mic gate via `is_playing`, sounddevice output."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Iterator

import numpy as np
import sounddevice as sd

from heckler.config import HecklerConfig

logger = logging.getLogger(__name__)


class SpeakerError(Exception):
    """Raised when TTS synthesis fails (distinct from other pipeline errors)."""


class Speaker:
    def __init__(self, config: HecklerConfig) -> None:
        """
        Loads KPipeline at init time (slow, do once).
        lang_code='a' for American English.
        Stores is_playing as threading.Event — shared with AudioCapture.
        """
        self._config = config
        self.is_playing: threading.Event = threading.Event()
        logger.info("downloading TTS model")
        from kokoro import KPipeline

        self._pipeline = KPipeline(lang_code="a")

    def speak(self, comment: str) -> float:
        """
        Full synthesis and playback. Returns tts_latency_ms (synthesis time only,
        not playback duration).

        Steps:
        1. self.is_playing.set()  ← gate mic before synthesis starts
        2. Synthesize: generator = self._pipeline(comment, voice=config.kokoro_voice, speed=config.kokoro_speed)
        3. Collect all audio chunks into single np array
        4. sounddevice.play(audio, samplerate=24000, blocking=True)
        5. self.is_playing.clear()  ← ungate mic after playback ends

        On synthesis error: clear is_playing, log, re-raise as SpeakerError.
        """
        self.is_playing.set()
        t0 = time.perf_counter()
        try:
            generator = self._pipeline(
                comment,
                voice=self._config.kokoro_voice,
                speed=self._config.kokoro_speed,
            )
            audio = self._collect_audio(generator)
        except Exception as e:
            self.is_playing.clear()
            logger.exception("TTS synthesis failed")
            raise SpeakerError("TTS synthesis failed") from e

        tts_latency_ms = (time.perf_counter() - t0) * 1000.0

        try:
            sd.play(audio, samplerate=24000, blocking=True)
        finally:
            self.is_playing.clear()

        return tts_latency_ms

    def _collect_audio(self, generator: Iterator[Any]) -> np.ndarray:
        """
        Kokoro yields (graphemes, phonemes, audio_chunk) tuples.
        We only care about audio_chunk (float32 numpy array, 24kHz mono).
        Concatenate all chunks into one array for gapless playback.
        """
        chunks: list[np.ndarray] = []
        for item in generator:
            if not isinstance(item, tuple) or len(item) != 3:
                raise ValueError(
                    "expected (graphemes, phonemes, audio_chunk) tuple from Kokoro"
                )
            _, _, audio_chunk = item
            if not isinstance(audio_chunk, np.ndarray):
                raise ValueError("Kokoro audio_chunk must be a numpy.ndarray")
            chunks.append(np.asarray(audio_chunk, dtype=np.float32))
        if not chunks:
            raise ValueError("no audio chunks produced by Kokoro pipeline")
        return np.asarray(np.concatenate(chunks), dtype=np.float32)
