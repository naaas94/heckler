from __future__ import annotations

import dataclasses
import json
import threading
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from heckler.config import HecklerConfig
from heckler.models import HeckleEvent


def _coerce_json(value: Any) -> Any:
    """Recursively coerce enums to string values and strip ``audio_chunk`` keys."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {
            k: _coerce_json(v)
            for k, v in value.items()
            if k != "audio_chunk"
        }
    if isinstance(value, (list, tuple)):
        return [_coerce_json(x) for x in value]
    return value


class HecklerLogger:
    def __init__(self, config: HecklerConfig) -> None:
        """
        Creates log_dir if not exists.
        Log path pattern: ``{log_dir}/heckler_{YYYY-MM-DD}.jsonl`` (file opened per append on each event).
        """
        self._log_dir = Path(config.log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path_for_date(self, d: date) -> Path:
        return self._log_dir / f"heckler_{d.isoformat()}.jsonl"

    def log_event(self, event: HeckleEvent) -> None:
        """
        Serializes HeckleEvent to JSON and appends to log file.
        Uses dataclasses.asdict() then coerces enums to .value strings.
        Adds newline after each record.
        Thread-safe.
        """
        line = self._serialize(event)
        path = self._path_for_date(date.today())
        with self._lock:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def _serialize(self, event: HeckleEvent) -> str:
        d = dataclasses.asdict(event)
        d.pop("audio_chunk", None)
        payload = _coerce_json(d)
        return json.dumps(payload, ensure_ascii=False)
