# Decision log — gui-launcher T3 (PyQt6 GUI + packaging)

## Chosen approach

- **`heckler/gui/`** package: `SignalBridge` (`QObject` + `pyqtSignal`) implements `ControllerCallbacks` so worker-thread callbacks emit Qt signals; `HecklerMainWindow` connects slots on the GUI thread only.
- **Model load:** `ModelLoadThread` (`QThread`) calls `PipelineController.load_models`; the main window stays responsive under `QApplication.exec()` while the loader thread runs. Loader OS thread name set to **`heckler-gui-loader`** (via `threading.current_thread().name` inside `run()`).
- **UX:** Start/stop gated until `load_models` finishes (`set_models_ready`). Mode radios disabled while running. Persona combo enabled only in running persona mode. **Export** opens the configured transcripts directory (markdown export still occurs on **stop** in `PipelineController`, unchanged).
- **Dependencies:** `PyQt6>=6.5` in runtime `[project] dependencies`; `pytest-qt>=4.2` in optional **`dev`** (resolves context-map Flag 4 — pytest-Qt infrastructure).

## Alternatives rejected

- **Modal `QProgressDialog.exec()` during startup:** avoids a nested `QEventLoop` but would block the primary event loop if misused; instead the main window is shown immediately with a status-bar “loading” state and a **non-blocking** `QThread` for `load_models`.
- **Calling `load_models()` on the GUI thread:** rejected — violates T3 kill criterion (2) and would freeze the UI for multi-second model init.

## Assumptions made

- **`prompts/`** root is resolved as `Path(heckler/gui/main_window.py).parent.parent.parent / "prompts"` — same layout as `PipelineController` (which uses `heckler/controller.py` → parent.parent / `"prompts"`).
- Operators use a supported CPython in **`requires-python`** (`>=3.11,<3.13`) for the full torch/CUDA stack; PyQt6 was smoke-installed on a wider interpreter for development only.

## Items deferred

- **End-to-end GUI test** with a real `PipelineController`, CUDA/torch, and audio hardware — out of scope for this packet (tests use mocks + offscreen Qt only).
- **Automated CI wiring** for `QT_QPA_PLATFORM=offscreen` — no `.github/` workflows in-repo; documented in `tests/test_gui.py` module docstring.

## Files added

- `tests/test_gui.py` (conventional `tests/test_<module>.py` mirror for `heckler/gui/`).
