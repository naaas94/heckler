"""Thread-local correlation metadata for LiteLLM completion tracing (reaction worker).

Values are optional string key/value pairs (e.g. response ids). Consumers serialize to JSON
when persisting alongside ``HeckleEvent`` rows (see ``heckler/event_store.insert_event_row``).
"""

from __future__ import annotations

import threading
from typing import Mapping

_local = threading.local()


def set_correlation(metadata: Mapping[str, str] | None) -> None:
    """Replace thread-local correlation; ``None`` clears."""
    if metadata is None:
        clear_correlation()
        return
    _local.data = dict(metadata)


def get_correlation() -> dict[str, str] | None:
    """Return a copy of thread-local correlation, or ``None`` if unset."""
    data = getattr(_local, "data", None)
    if data is None:
        return None
    return dict(data)


def clear_correlation() -> None:
    """Remove thread-local correlation for this thread."""
    if hasattr(_local, "data"):
        delattr(_local, "data")


def reset_correlation() -> None:
    """Alias for :func:`clear_correlation` (symmetry with future wider reset hooks)."""
    clear_correlation()
