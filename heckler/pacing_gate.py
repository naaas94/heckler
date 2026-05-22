"""Minimum-interval pacing between spoken outputs with optional high-score override."""

from __future__ import annotations

import threading
import time

from heckler.config import HecklerConfig


class PacingGate:
    def __init__(self, config: HecklerConfig) -> None:
        self._config = config
        self._last_output_time: float = 0.0
        self._lock: threading.Lock = threading.Lock()

    def _cooldown_state_locked(self) -> tuple[bool, float]:
        """Elapsed/interval math; caller must hold ``self._lock``."""
        elapsed = time.time() - self._last_output_time
        interval = self._config.min_output_interval_s
        in_cooldown = elapsed < interval
        cooldown_remaining = max(0.0, interval - elapsed)
        return in_cooldown, cooldown_remaining

    def cooldown_status(self) -> tuple[bool, float]:
        """
        Returns (in_cooldown, cooldown_remaining) using the same elapsed/interval math
        as evaluate(), without reading score or score_override_threshold.
        """
        with self._lock:
            return self._cooldown_state_locked()

    def evaluate(self, score: float) -> tuple[bool, float]:
        """
        Returns (should_speak, cooldown_remaining).
        cooldown_remaining: seconds left in cooldown at eval time (0.0 if not in cooldown).

        Logic:
          (in_cooldown, cooldown_remaining) from cooldown_status math
          if not in_cooldown: return True, 0.0
          if score >= config.score_override_threshold: return True, cooldown_remaining
          return False, cooldown_remaining

        Coupling (T9): record_output() must be invoked on the pipeline immediately before
        TTS synthesis begins (before speaker.speak()), not after playback ends, so the
        cooldown reflects intent to avoid stacked outputs rather than audio duration.
        """

        with self._lock:
            in_cooldown, cooldown_remaining = self._cooldown_state_locked()
            if not in_cooldown:
                return True, 0.0
            if score >= self._config.score_override_threshold:
                return True, cooldown_remaining
            return False, cooldown_remaining

    def record_output(self) -> None:
        """
        Call immediately before TTS synthesis begins, not after playback ends.
        Rationale: cooldown intent is "don't stack outputs"; if we wait for
        playback to finish, a 3-second TTS output creates an unintended 3s
        offset in the effective interval.
        Thread-safe.

        Coupling (T9): must be called BEFORE speaker.speak(), not after playback completes.
        """

        with self._lock:
            self._last_output_time = time.time()
