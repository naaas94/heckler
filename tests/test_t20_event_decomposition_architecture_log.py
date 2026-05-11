"""Regression guards for `.dev/decision-logs/T20-event-decomposition-arch.md` (T1 freeze).

**Adversarial gap (not covered):** These tests do not judge whether each **Landed** answer
remains the *correct* product policy—only that the T1 packet kill criterion "every flag
has an explicit landed answer" cannot be silently deleted. Wrong policy text is caught by
orchestrator / owner review, not by grep.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
T20_PATH = _REPO_ROOT / ".dev" / "decision-logs" / "T20-event-decomposition-arch.md"

_FLAG_HEADINGS = (
    "### Flag 1 — Source of truth (SSOT)",
    "### Flag 2 — Migration posture",
    "### Flag 3 — Eval / labels / prompt metadata",
    "### Flag 4 — Vocabulary: “eval”",  # U+201C / U+201D around eval
    "### Flag 5 — Import / backfill tests",
    "### Flag 6 — `reactor_result` physical layout",
)


def test_t20_architecture_log_exists() -> None:
    assert T20_PATH.is_file(), "T20 architecture decision log is missing"


def _section_after_heading(text: str, heading: str) -> str:
    assert heading in text, f"missing section heading: {heading!r}"
    start = text.index(heading)
    rest = text[start + len(heading) :]
    next_break = rest.find("\n### ")
    return rest if next_break == -1 else rest[:next_break]


@pytest.mark.parametrize("heading", _FLAG_HEADINGS)
def test_t20_each_flag_has_landed(heading: str) -> None:
    text = T20_PATH.read_text(encoding="utf-8")
    chunk = _section_after_heading(text, heading)
    assert "**Landed:**" in chunk, f"{heading!r} missing **Landed:** bullet"


def test_t20_frozen_child_and_eval_table_names() -> None:
    text = T20_PATH.read_text(encoding="utf-8")
    assert "event_reactor_results" in text
    assert "heckler_eval_labels" in text


def test_t20_alignment_binds_serialize_contract() -> None:
    """Falsifier: deleting the §2 alignment note that preserves model JSON semantics."""
    text = T20_PATH.read_text(encoding="utf-8")
    assert "## Alignment with shared contract §2" in text
    assert "serialize_heckle_event" in text
    assert "heckle_event_from_json_dict" in text
