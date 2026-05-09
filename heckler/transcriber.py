from __future__ import annotations

import logging
import queue
import uuid
from faster_whisper import WhisperModel

from heckler.config import HecklerConfig
from heckler.models import AudioChunk

logger = logging.getLogger(__name__)

_QueueItem = AudioChunk | tuple[str, AudioChunk] | None


class Transcriber:
    """faster-whisper wrapper: AudioChunk in, transcript text out (per chunk, no cross-chunk context)."""

    def __init__(self, config: HecklerConfig) -> None:
        """
        Loads WhisperModel at init time. This takes 3–8 seconds on first run
        (model download + CUDA initialization). After first load, subsequent
        startups use the cached model from ~/.cache/huggingface/.
        Log a clear "loading transcription model..." message so the operator
        knows startup is not hung.
        """
        logger.info(
            "[HECKLER] Loading transcription model (%s / %s)...",
            config.whisper_model_size,
            config.whisper_compute_type,
        )
        try:
            self._config = config
            self.model = WhisperModel(
                config.whisper_model_size,
                device="cuda",
                compute_type=config.whisper_compute_type,
            )
        except Exception:
            logger.exception(
                "[HECKLER] Failed to load transcription model (%s).",
                config.whisper_model_size,
            )
            raise
        logger.info("[HECKLER] Transcription model ready.")

    def transcribe(self, chunk: AudioChunk) -> str:
        """
        Synchronous. Runs faster-whisper on chunk.audio.
        Returns transcript string. Empty string if VAD passes but whisper
        produces no segments (silence artifact).

        Implementation:
        segments, info = self.model.transcribe(
            chunk.audio,
            beam_size=config.whisper_beam_size,
            language=config.whisper_language,
            vad_filter=True,
            word_timestamps=False,
            condition_on_previous_text=False  # IMPORTANT: no context leakage
        )
        return " ".join(seg.text.strip() for seg in segments)
        """
        segments, _info = self.model.transcribe(
            chunk.audio,
            beam_size=self._config.whisper_beam_size,
            language=self._config.whisper_language,
            vad_filter=True,
            word_timestamps=False,
            condition_on_previous_text=False,
        )
        return " ".join(seg.text.strip() for seg in segments)

    def run(self, in_queue: queue.Queue, out_queue: queue.Queue) -> None:
        """
        Blocking loop. Called in its own thread by pipeline.py.
        Drains in_queue, transcribes, puts (utterance_id, transcript) to out_queue.
        """
        while True:
            item: _QueueItem = in_queue.get()
            if item is None:
                break
            if isinstance(item, tuple):
                utterance_id, chunk = item
            else:
                chunk = item
                utterance_id = str(uuid.uuid4())
            text = self.transcribe(chunk).strip()
            out_queue.put((utterance_id, text))
