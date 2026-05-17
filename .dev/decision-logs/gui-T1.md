# Decision Log — T1: PipelineController + hot-swap + callback infrastructure

**Plan:** gui-launcher  
**Subtask:** T1  
**Date:** 2026-05-17  
**Log tier:** architectural

---

## Chosen approach

### Controller extraction strategy
Extracted `PipelineController` into `heckler/controller.py` as a class that owns the full pipeline lifecycle (start/stop/mode-switch/persona-swap). The class holds references to the two heavy models (`Transcriber`, `Speaker`) across mode switches, reconstructs only mode-specific objects (`Reactor`, queues, capture) on each `start()` call. Worker functions remain in `heckler/pipeline.py`; the controller imports and runs them in threads.

### ReactorHolder
Implemented as a class wrapping a `Reactor` reference behind a `threading.Lock`. The lock prevents torn reads under free-threaded Python (PEP 703). Under CPython with the GIL, attribute assignment is already atomic, but the explicit lock makes the contract testable and future-proof. Workers call `reactor_holder.get()` at the start of each iteration; any in-progress `react()` call completes with the old reactor, and the next call uses the new one.

### Circular import avoidance
`pipeline.py` requires `ReactorHolder` for the `_run_reaction_worker` signature and `main()` wiring. To avoid a circular import (`pipeline` ↔ `controller`), two mechanisms are used:
1. The type annotation `reactor_holder: ReactorHolder` in `_run_reaction_worker` is a lazy string (via `from __future__ import annotations`) with `ReactorHolder` imported only under `TYPE_CHECKING` in `pipeline.py`.
2. `main()` in `pipeline.py` imports `ReactorHolder` inside the function body: `from heckler.controller import ReactorHolder`.

At runtime, `pipeline.py` does not import from `controller.py` at module level; `controller.py` imports from `pipeline.py` at module level. No circular dependency.

### Callback routing for worker → GUI
Three worker functions gained optional `on_transcript` / `on_reaction` callbacks (all default to `None`). When `None`, the workers behave exactly as before (existing CLI `main()` behavior preserved). When provided by the controller, callbacks route live output to the GUI. Exceptions in callbacks are caught per-worker so a raising callback cannot kill the worker thread.

- `_run_transcribe_worker`: `on_transcript` replaces the `print("[TRANSCRIBE] ...")` statement (conditional: print only when callback is `None`).
- `_run_transcription_worker`: `on_transcript` fires after an utterance passes the density gate and is enqueued to the reaction queue.
- `_run_reaction_worker`: `on_reaction(result, was_spoken)` fires when a `ReactorResult` is produced (score gate passed); `was_spoken` is `True` on successful TTS, `False` on pacing-gate rejection or TTS failure. Does not fire when `result is None` (LLM_ERROR, SCORE_GATE).

### Stop sequence (persona mode)
`stop()` follows the same two-phase sentinel protocol as the original `main()`:
1. `capture.stop()` — no more audio entering `audio_queue`
2. Sentinel → `audio_queue` — transcription worker exits after draining
3. `transcription_thread.join(timeout=120s)` — ensures no more utterances enter `reaction_queue`
4. Sentinel → `reaction_queue` — reaction worker exits after draining
5. `reaction_thread.join(timeout=120s)` — pipeline fully quiesced

---

## Alternatives rejected

### Option A — Keep ReactorHolder in pipeline.py
Would avoid the circular import entirely. Rejected: the contract (§2) explicitly places `ReactorHolder` in `controller.py` as a T1-owned type. Moving it would violate the shared contract and make T2/T3 imports inconsistent.

### Option B — Use a shared types module (e.g. heckler/types.py)
Would hold `ReactorHolder`, `ControllerCallbacks`, etc., referenced by both `pipeline.py` and `controller.py` without circularity. Rejected: adds a file not in **Files to touch** and changes the import path for T2/T3 consumers from `heckler.controller` to `heckler.types`. Contract names `heckler/controller.py` as the owner; changing the module is an orchestrator-level decision.

### Option C — Duplicate worker logic in controller.py
Have the controller inline its own versions of the worker functions rather than importing from `pipeline.py`. Rejected: duplicates logic, diverges from the tested pipeline workers, and eliminates the transitional compatibility that lets `main()` and `PipelineController` share the same worker code.

---

## Assumptions made

1. **Python GIL makes Reactor reference assignment atomic between worker iterations.** Under CPython, the lock in `ReactorHolder` is belt-and-suspenders; under free-threaded Python (PEP 703), it becomes the sole correctness guarantee. The lock is always taken.

2. **Worker threads consume shutdown sentinels reliably within 120s.** If a worker is blocked on a long LLM API call, mode switch or stop can hang for up to 120s. This is acceptable at this stage (T3 will add UI feedback for the wait).

3. **Transcriber and Speaker hold no mode-specific mutable state across calls.** If either caches mode-shape-dependent buffers, sharing them across mode switches could cause subtle audio bugs. Verified by inspection: `Transcriber` stateless per-call; `Speaker` stateless per-call (no persistent playback state beyond `is_playing` event).

4. **AudioCapture.stop() reliably joins its internal thread within 5s.** `AudioCapture.stop()` calls `thread.join(timeout=5.0)`. If the sounddevice InputStream hangs on a WASAPI driver bug, mode switch hangs with no recourse. No timeout is currently available beyond the 5s join in `AudioCapture` itself.

---

## Items deferred

- **`on_transcript` callback fires after density gate pass in persona mode.** Density-failing transcripts are not surfaced to the GUI. If the GUI needs to show "heard but rejected" speech, a second callback (`on_density_fail`) would be needed. Deferred — not required by T2/T3 contracts.

- **Export path for transcribe-mode session uses session_label, not session_id.** The export filename is `{label}.md` (matching the original `main()` behavior). If two sessions share a label, the file is overwritten. Deferred — no session-conflict handling in scope for T1 or T2.

- **`AudioCapture.stop()` timeout observability.** If the capture thread doesn't stop within 5s, `stop()` silently continues. No `on_error` callback is fired. Adding that observability requires changes to `AudioCapture` (not in Files to touch). Deferred to a future subtask.

- **`load_models()` called before `start()` assertion.** Currently an `AssertionError` (internal invariant). A cleaner design would be a dedicated `ModelNotLoadedError`. Deferred — the assertion is sufficient for the controller's current consumers (T2/T3 will call `load_models()` before `start()` by construction).
