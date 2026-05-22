"""TTS playback: Kokoro synthesis, mic gate via `is_playing`, sounddevice output."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Iterator

import numpy as np
import sounddevice as sd
import torch

from heckler.config import HecklerConfig

logger = logging.getLogger(__name__)


class SpeakerError(Exception):
    """Raised when TTS synthesis fails (distinct from other pipeline errors)."""


class Speaker:
    def __init__(self, config: HecklerConfig) -> None:
        """
        Loads KPipeline at init time (slow, do once).
        Kokoro phonemizer language comes from ``config.kokoro_lang_code`` (resolved from ``locale``).
        Stores is_playing as threading.Event — shared with AudioCapture.
        """
        self._config = config
        self.is_playing: threading.Event = threading.Event()
        logger.info("downloading TTS model")
        from kokoro import KPipeline

        self._pipeline = KPipeline(lang_code=config.kokoro_lang_code)

    def speak(self, comment: str) -> float:
        """
        Full synthesis and playback. Returns tts_latency_ms (synthesis time only,
        not playback duration).

        Steps:
        1. self.is_playing.set()  ← gate mic before synthesis starts
        2. Synthesize: generator = self._pipeline(comment, voice=config.kokoro_voice, speed=config.kokoro_speed)
        3. Collect all audio chunks into single np array
        4. sounddevice.play(audio, samplerate=24000, blocking=True)
        5. Optional post-playback tail sleep (`tts_gate_tail_ms`) while gate stays set
        6. self.is_playing.clear()  ← ungate mic after playback and acoustic tail

        On synthesis error: clear is_playing, log, re-raise as SpeakerError.
        On play failure: clear without tail sleep.
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
            tail_ms = self._config.tts_gate_tail_ms
            if tail_ms > 0:
                time.sleep(tail_ms / 1000.0)
        finally:
            self.is_playing.clear()

        return tts_latency_ms

    def _collect_audio(self, generator: Iterator[Any]) -> np.ndarray:
        """
        Kokoro yields ``KPipeline.Result`` objects (``.audio``) or, for older
        versions, ``(graphemes, phonemes, audio_chunk)`` tuples. Audio may be
        ``numpy.ndarray`` or ``torch.FloatTensor`` (24 kHz mono). Concatenate
        all chunks into one array for gapless playback.
        """
        chunks: list[np.ndarray] = []
        for item in generator:
            if hasattr(item, "audio") and not isinstance(item, tuple):
                raw = item.audio
            elif isinstance(item, tuple) and len(item) == 3:
                raw = item[2]
            else:
                raise ValueError(
                    "expected Kokoro KPipeline.Result or (graphemes, phonemes, audio) tuple"
                )
            if raw is None:
                raise ValueError("Kokoro chunk has no audio (None)")
            if isinstance(raw, torch.Tensor):
                chunks.append(
                    np.asarray(raw.detach().cpu().numpy(), dtype=np.float32)
                )
            elif isinstance(raw, np.ndarray):
                chunks.append(np.asarray(raw, dtype=np.float32))
            else:
                raise ValueError(
                    "Kokoro audio must be a numpy.ndarray or torch.Tensor"
                )
        if not chunks:
            raise ValueError("no audio chunks produced by Kokoro pipeline")
        return np.asarray(np.concatenate(chunks), dtype=np.float32)
