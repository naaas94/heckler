# Executor Packet — T10-remediation: Audit F-03 + F-05

---

## Scope

Close two audit findings from `.dev/audits/2026-05-08-heckler-v1.md`:

- **F-03 (major / coverage-gap):** No test exercises `main()`'s `finally` shutdown path — `capture.stop()`, sentinel enqueue into both queues, `transcription_thread.join()`, `reaction_thread.join()`. T9 kill criterion requires proper thread joins on shutdown.
- **F-05 (minor / contract-violation drift):** `pipeline.py` line 122 uses `assert discard_reason is not None` inside `_run_reaction_worker`. If `reactor.react()` ever regressed to `(None, latency, None)`, this kills the worker thread with `AssertionError`, bypassing the structured `HeckleEvent` logging path. Replace with a defensive fallback.

**Not in scope:** Decision log staleness (F-01, F-02), shallow JSON regex (F-04). Documentation-only.

---

## Files to touch

| File | Change |
|---|---|
| `heckler/pipeline.py` | Replace `assert discard_reason is not None` with defensive fallback |
| `tests/test_pipeline.py` | Add shutdown-join test for `main()`'s `finally` block |

---

## F-05 fix — `heckler/pipeline.py`

In `_run_reaction_worker`, find:

```python
if result is None:
    assert discard_reason is not None
```

Replace with:

```python
if result is None:
    if discard_reason is None:
        logger.error(
            "reactor.react() returned (None, %s, None) — contract violation; "
            "falling back to LLM_ERROR",
            llm_latency_ms,
        )
        discard_reason = DiscardReason.LLM_ERROR
```

This preserves the worker thread, logs the violation, and falls through to the existing `HeckleEvent` construction that uses `discard_reason`.

---

## F-03 fix — `tests/test_pipeline.py`

Add a test that drives `main()` through its full startup → KeyboardInterrupt → finally shutdown path with all heavy components mocked.

**Strategy:**

1. Monkeypatch `load_config` to return a default `HecklerConfig(anthropic_api_key="test")`.
2. Monkeypatch constructors for `Transcriber`, `Speaker`, `Reactor`, `HecklerLogger`, `AudioCapture` to return `MagicMock` instances. `Speaker` mock must expose `is_playing = threading.Event()`.
3. Monkeypatch `time.sleep` to raise `KeyboardInterrupt` immediately (the `while True: time.sleep(0.1)` loop in `main()`).
4. Subclass `threading.Thread` to track created threads, monkeypatch it into `heckler.pipeline.threading.Thread`.
5. Call `main([])`.
6. Assert:
   - `capture_mock.stop()` was called (mic released)
   - `main()` returned (did not hang — proves both joins completed)
   - All tracked threads report `is_alive() == False` after return

**Skeleton:**

```python
def test_main_shutdown_stops_capture_and_joins_threads(monkeypatch):
    import threading as _threading

    cfg = HecklerConfig(anthropic_api_key="test-key")
    monkeypatch.setattr("heckler.pipeline.load_config", lambda: cfg)
    monkeypatch.setattr("heckler.pipeline.HecklerLogger", lambda _: MagicMock())

    mock_transcriber = MagicMock()
    mock_transcriber.transcribe.return_value = ""
    monkeypatch.setattr("heckler.pipeline.Transcriber", lambda _: mock_transcriber)

    mock_speaker = MagicMock()
    mock_speaker.is_playing = _threading.Event()
    monkeypatch.setattr("heckler.pipeline.Speaker", lambda _: mock_speaker)
    monkeypatch.setattr("heckler.pipeline.Reactor", lambda _: MagicMock())

    mock_capture = MagicMock()
    monkeypatch.setattr(
        "heckler.pipeline.AudioCapture", lambda *a, **kw: mock_capture
    )

    # Interrupt the main loop on first sleep
    monkeypatch.setattr("heckler.pipeline.time.sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt))

    # Track threads to verify they were joined
    spawned: list[_threading.Thread] = []
    _OrigThread = _threading.Thread

    class _TrackingThread(_OrigThread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            spawned.append(self)

    monkeypatch.setattr("heckler.pipeline.threading.Thread", _TrackingThread)

    main([])

    mock_capture.stop.assert_called_once()
    assert len(spawned) == 2
    for t in spawned:
        assert not t.is_alive(), f"Thread {t.name} still alive after main() returned"
```

**Notes:**
- Workers start, immediately block on empty queues. The `finally` block sends sentinels that unblock them. Both exit cleanly.
- `time.sleep` patch is scoped to `heckler.pipeline.time.sleep` (module-level import). Workers don't call `time.sleep`, so no interference.
- The `time.perf_counter()` calls for startup banners still work (not patched).
- The 120s join timeout in production code is more than enough; workers exit in microseconds with mocked components.

---

## Kill criteria

- HALT if `assert discard_reason is not None` still exists in `pipeline.py`.
- HALT if the new test does not exercise `capture.stop()` and both thread joins.
- HALT if any existing test regresses.

---

## Contract bindings

No §2 contracts changed. No coupling surfaces affected. This is a coverage + hardening patch only.
