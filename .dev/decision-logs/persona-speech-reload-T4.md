# Decision log — persona-speech-reload T4: ModelLoadThread ownership

**Date:** 2026-05-22  
**Subtask:** T4 (persona-speech-reload plan)  
**Supersedes:** locale-lang-propagation-T7.md (ModelLoadThread reads config.persona_name at init)

## Decision: Callable snapshots read at `run()` time

Landed: `ModelLoadThread` constructor accepts `persona_name_fn: Callable[[], str]` and `locale_override_fn: Callable[[], str | None]`. These are called at the start of `run()` to capture the combo state at thread-start time (not init time).

## Alternatives rejected

**A. Pass `HecklerMainWindow` directly to `ModelLoadThread`.**  
Rejected: creates module-level coupling (app.py imports main_window.py class); QThread holding a reference to a QWidget introduces ownership ambiguity. Callable pattern is lower coupling.

**B. Capture snapshot at `__init__` time (same as before but from combo).**  
Rejected: the window exists before the thread starts, but the user may still change the combo between construction and `run()`. At-run-time read is the only safe contract. D7 (Start correction) covers the residual race after `run()` completes.

## Deferred

- D7: if `ModelLoadThread` finishes with a stale persona (combo changed after thread started), Start correction (`ensure_heavy_models` in `_on_start_stop`) catches the mismatch.
