from __future__ import annotations

import queue
import threading
import time
from collections import deque
from typing import Any, Callable, Optional

import numpy as np
import sounddevice as sd
import torch

from heckler.config import HecklerConfig
from heckler.models import AudioChunk

# Silero VAD at 16 kHz expects fixed 512-sample frames (see snakers4/silero-vad).
VAD_FRAME_SAMPLES = 512


def _put_drop_oldest(q: queue.Queue, item: Any) -> None:
    """Enqueue ``item``; if ``q`` is full, remove the oldest entry and retry."""
    while True:
        try:
            q.put_nowait(item)
            return
        except queue.Full:
            try:
                q.get_nowait()
            except queue.Empty:
                pass


class AudioCapture:
    """Microphone capture with Silero VAD segmentation; enqueues ``AudioChunk`` on silence boundaries."""

    def __init__(
        self,
        config: HecklerConfig,
        out_queue: queue.Queue,
        is_playing: threading.Event,
    ) -> None:
        self._config = config
        self._out_queue = out_queue
        self._is_playing = is_playing

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._pcm_lock = threading.Lock()
        self._pcm: deque[np.ndarray] = deque(maxlen=256)

        self._callback: Callable[..., None] = self._vad_callback

    def start(self) -> None:
        """Starts capture in a background thread. Non-blocking."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._capture_loop, name="heckler-audio-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signals capture thread to stop. Blocks until thread joins."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _emit_audio_segment(self, audio: np.ndarray, min_speech_samples: int) -> None:
        """Validate segment, respect ``is_playing`` gate, enqueue with drop-oldest overflow policy."""
        if audio.size == 0:
            return
        if audio.dtype != np.float32 or audio.ndim != 1:
            raise TypeError("AudioChunk.audio must be float32 numpy 1D")
        if audio.shape[0] < min_speech_samples:
            return
        if self._is_playing.is_set():
            return
        chunk = AudioChunk(audio=audio, captured_at=time.time())
        _put_drop_oldest(self._out_queue, chunk)

    def _vad_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        """sounddevice callback — must be fast, no blocking I/O here."""
        _ = frames, time_info, status
        mono = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
        with self._pcm_lock:
            self._pcm.append(mono.astype(np.float32, copy=False))

    def _capture_loop(self) -> None:
        """
        Internal. Runs in background thread.
        Opens sounddevice InputStream with callback.
        On each VAD-boundary, constructs AudioChunk and puts to out_queue.
        If out_queue is full (maxsize reached), drops oldest item (not newest).
        """
        if self._config.sample_rate != 16_000:
            raise ValueError("HECKLER requires sample_rate=16000 for Silero VAD and Whisper")

        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
        )
        utils_tuple = tuple(utils)
        if len(utils_tuple) < 4:
            raise RuntimeError(f"Unexpected silero-vad utils length: {len(utils_tuple)}")
        _ = (utils_tuple[0], utils_tuple[1], utils_tuple[2])
        VADIterator = utils_tuple[3]

        vad_iter = VADIterator(
            model,
            threshold=self._config.vad_threshold,
            sampling_rate=self._config.sample_rate,
            min_silence_duration_ms=self._config.silence_duration_ms,
        )

        min_speech_samples = int(self._config.sample_rate * self._config.min_speech_duration_ms / 1000)
        max_speech_samples = int(self._config.sample_rate * self._config.max_speech_duration_s)

        capturing = False
        segment: list[np.ndarray] = []

        device = self._config.capture_device

        def new_vad_iterator() -> Any:
            return VADIterator(
                model,
                threshold=self._config.vad_threshold,
                sampling_rate=self._config.sample_rate,
                min_silence_duration_ms=self._config.silence_duration_ms,
            )

        with sd.InputStream(
            device=device,
            channels=1,
            dtype="float32",
            samplerate=self._config.sample_rate,
            blocksize=VAD_FRAME_SAMPLES,
            callback=self._callback,
        ):
            while not self._stop.is_set():
                frames = self._drain_pcm_batch()
                if not frames:
                    time.sleep(0.005)
                    continue
                for frame in frames:
                    if frame.shape[0] != VAD_FRAME_SAMPLES:
                        continue
                    tensor = torch.from_numpy(frame)

                    if capturing:
                        pending = sum(f.shape[0] for f in segment) + int(frame.shape[0])
                        if pending >= max_speech_samples:
                            audio = np.concatenate(segment + [frame.copy()], dtype=np.float32)
                            self._emit_audio_segment(audio, min_speech_samples)
                            capturing = False
                            segment = []
                            vad_iter = new_vad_iterator()
                            ev = vad_iter(tensor)
                        else:
                            ev = vad_iter(tensor)
                    else:
                        ev = vad_iter(tensor)

                    if isinstance(ev, dict) and "start" in ev:
                        capturing = True
                        segment = [frame.copy()]
                        continue

                    if capturing:
                        segment.append(frame.copy())

                    if isinstance(ev, dict) and "end" in ev:
                        capturing = False
                        audio = np.concatenate(segment, dtype=np.float32) if segment else np.array([], dtype=np.float32)
                        segment = []
                        self._emit_audio_segment(audio, min_speech_samples)

    def _drain_pcm_batch(self) -> list[np.ndarray]:
        out: list[np.ndarray] = []
        with self._pcm_lock:
            while self._pcm:
                out.append(self._pcm.popleft())
        return out
