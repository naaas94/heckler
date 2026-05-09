from __future__ import annotations

import threading
from collections import deque


class ContextBuffer:
    def __init__(self, maxlen: int) -> None:
        self._buffer: deque[str] = deque(maxlen=maxlen)
        self._lock: threading.Lock = threading.Lock()

    def push(self, transcript: str) -> None:
        """Thread-safe append."""
        with self._lock:
            self._buffer.append(transcript)

    def get_context_block(self) -> str:
        """
        Returns the last N transcripts formatted as a numbered block:
        [1] first utterance
        [2] second utterance
        ...
        [N] most recent utterance

        Returns empty string if buffer is empty.
        """
        with self._lock:
            items = list(self._buffer)
        if not items:
            return ""
        lines = [f"[{i}] {text}" for i, text in enumerate(items, start=1)]
        return "\n".join(lines)
