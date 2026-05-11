from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from heckler.config import HecklerConfig
from heckler.event_store import init_schema, insert_heckle_event_row, open_store
from heckler.models import HeckleEvent, serialize_heckle_event
from heckler.tracing_context import clear_correlation, get_correlation

_log = logging.getLogger(__name__)


class HecklerLogger:
    def __init__(self, config: HecklerConfig) -> None:
        """Open SQLite at ``config.sqlite_database_path`` and ensure schema exists."""
        db_path = Path(config.sqlite_database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = open_store(db_path)
        init_schema(self._conn)

    def log_event(self, event: HeckleEvent) -> None:
        """Persist ``event``: ``payload_json`` plus normalized columns and optional reactor row.

        Uses a single SQLite transaction per call; holds :attr:`_lock` for the duration.
        """
        payload_json = json.dumps(serialize_heckle_event(event), ensure_ascii=False)
        corr = get_correlation()
        correlation_json = (
            json.dumps(corr, ensure_ascii=False) if corr is not None else None
        )
        try:
            with self._lock:
                insert_heckle_event_row(
                    self._conn,
                    event=event,
                    payload_json=payload_json,
                    correlation_json=correlation_json,
                )
        except Exception as exc:
            _log.error("SQLite event insert failed: %s", exc, exc_info=True)
            raise
        finally:
            clear_correlation()
