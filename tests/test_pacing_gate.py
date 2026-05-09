"""Tests for heckler.pacing_gate.PacingGate."""

from __future__ import annotations

import threading

from heckler.config import HecklerConfig
from heckler.pacing_gate import PacingGate


def test_first_call_no_cooldown(monkeypatch):
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 1000.0)
    gate = PacingGate(HecklerConfig())
    assert gate.evaluate(0.0) == (True, 0.0)


def test_within_cooldown_blocks_low_score(monkeypatch):
    cfg = HecklerConfig(min_output_interval_s=10.0)
    gate = PacingGate(cfg)
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 100.0)
    gate.record_output()
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 105.0)
    assert gate.evaluate(0.5) == (False, 5.0)


def test_after_cooldown_expires(monkeypatch):
    cfg = HecklerConfig(min_output_interval_s=10.0)
    gate = PacingGate(cfg)
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 100.0)
    gate.record_output()
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 111.0)
    assert gate.evaluate(0.0) == (True, 0.0)


def test_score_override_within_cooldown(monkeypatch):
    cfg = HecklerConfig(min_output_interval_s=10.0, score_override_threshold=0.9)
    gate = PacingGate(cfg)
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 100.0)
    gate.record_output()
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 105.0)
    assert gate.evaluate(0.95) == (True, 5.0)


def test_score_override_at_threshold_boundary(monkeypatch):
    cfg = HecklerConfig(min_output_interval_s=10.0, score_override_threshold=0.9)
    gate = PacingGate(cfg)
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 100.0)
    gate.record_output()
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 105.0)
    assert gate.evaluate(0.9) == (True, 5.0)


def test_score_below_override_threshold_blocked(monkeypatch):
    cfg = HecklerConfig(min_output_interval_s=10.0, score_override_threshold=0.9)
    gate = PacingGate(cfg)
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 100.0)
    gate.record_output()
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 105.0)
    assert gate.evaluate(0.89) == (False, 5.0)


def test_evaluate_concurrent_threads_consistent_results(monkeypatch):
    """Two threads calling evaluate() simultaneously see coherent cooldown math."""
    cfg = HecklerConfig(min_output_interval_s=10.0, score_override_threshold=0.9)
    gate = PacingGate(cfg)
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 100.0)
    gate.record_output()
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 105.0)

    results: list[tuple[bool, float]] = []
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        results.append(gate.evaluate(0.5))

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results) == 2
    assert results[0] == (False, 5.0)
    assert results[1] == (False, 5.0)


def test_evaluate_and_record_output_interleaved_under_load(monkeypatch):
    """
    Falsifier: interleaved record_output / evaluate without proper locking could
    deadlock, raise, or corrupt shared state under contention.
    """
    cfg = HecklerConfig(min_output_interval_s=10.0)
    gate = PacingGate(cfg)
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 1000.0)

    def run():
        for _ in range(500):
            gate.evaluate(0.2)
            gate.record_output()

    t1 = threading.Thread(target=run)
    t2 = threading.Thread(target=run)
    t1.start()
    t2.start()
    t1.join(timeout=10.0)
    t2.join(timeout=10.0)
    assert not t1.is_alive()
    assert not t2.is_alive()


def test_elapsed_equals_interval_exits_cooldown(monkeypatch):
    """Boundary: elapsed == min_output_interval_s must not stay in cooldown (< vs <=)."""
    cfg = HecklerConfig(min_output_interval_s=10.0)
    gate = PacingGate(cfg)
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 100.0)
    gate.record_output()
    monkeypatch.setattr("heckler.pacing_gate.time.time", lambda: 110.0)
    assert gate.evaluate(0.0) == (True, 0.0)
