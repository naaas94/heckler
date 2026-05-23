# Learning retrospective — gui-launcher

**Date:** 2026-05-23  
**Sources:** `.dev/archive/gui-launcher/plan.md` (v1.1), `context-map.md`, packets `T1.md`–`T5.md`, `.dev/decision-logs/gui-T1.md`, `gui-T3.md`, `.dev/audits/2026-05-17-gui-launcher.md`, methodology twin `.dev/retrospectives/methodology/2026-05-23-gui-launcher.md`, git history `58b0bb76` → `56c3748e` (initial land) and later controller/GUI commits on the same modules.

---

## 1. Task context

**What shipped (May 2026 arc):** A **PyQt6 desktop launcher** (`heckler-gui` → `heckler.gui.app:main`) plus a reusable **`PipelineController`** in `heckler/controller.py` with **`ReactorHolder`** for persona hot-swap, optional **worker callbacks** for live feeds, and **runtime mode switching** (persona ↔ transcribe) without reloading Whisper/Kokoro. The CLI entry `heckler` became a thin wrapper over the same controller; workers stayed in `heckler/pipeline.py`.

**Why this earns a learning retrospective:** Two **architectural** subtasks (controller extraction + Qt app), a **deferred integration surface** from persona-system and transcription-engine design docs, and a concrete lesson in **where risk actually lived** versus where the plan’s adversarial pass predicted it. The work also established a **stable product boundary** (`PipelineController` + `ControllerCallbacks`) that later plans (locale-lang-propagation, persona-speech-reload) extended without reopening the GUI package internals.

**Timeline anchor:** Exploration 2026-05-16 → execution/audit 2026-05-17 → plan tree archived 2026-05-22. Code at audit HEAD `56c3748e` had **66 passing tests**; audit verdict **`fail`** on provenance only, not on runtime contracts.

---

## 2. What I now understand that I didn’t before

### The controller is the real “GUI,” even when there is no window

Heckler’s blocking CLI was never “the product” — it was **accidental UI** (`print`, `sleep`, `KeyboardInterrupt`). The meaningful extraction was not “add PyQt6” but **name and own the lifecycle API** that both shells need: `load_models` / `start` / `stop` / `switch_mode` / `swap_persona`, with **heavy models pinned** and **light topology rebuilt**. Once that exists, the GUI is mostly **presentation and thread rules**; the hard concurrency story stays in the controller and the existing worker functions.

That reframing explains why putting `PipelineController` in `heckler/gui/` would have been a long-term mistake: the CLI is not a second-class consumer, and anything that imports Qt should stay downstream of a Qt-free module.

### Hot-swap is a *read pattern*, not a restart protocol

The persona-system design doc talked about “atomic Reactor replacement between utterances.” Before this task, `_run_reaction_worker` captured `reactor` once at thread start — so “swap” without restart was **impossible** regardless of GIL folklore. The fix is boring and correct: **`reactor_holder.get()` at the top of each loop iteration** (see `heckler/pipeline.py` around the reaction worker loop). An in-flight `react()` keeps the old instance; the next utterance sees the new one. The lock is not there to cancel work; it is there to make the contract **testable** and safe under PEP 703.

I had over-weighted “threading.Event + handoff” in pre-plan ask cards; the landed design is simpler and matches the actual boundary (“between utterances” = between queue items, not mid-`react()`).

### Mode switch is a small distributed system teardown

Persona mode and transcribe mode are not two flags on one loop — they are **different graphs**: thread count, queues, sqlite session, `is_playing` wiring (`speaker.is_playing` vs bare `threading.Event()`), and whether a reaction worker exists at all. Runtime mode switch therefore means **stop capture → sentinel joins → drop persona-only objects → rebuild → start capture**, while **never** reconstructing `Transcriber`/`Speaker` if you want sub-minute toggles.

The pre-plan context map’s coupling surfaces 1–6 were the right mental model; the plan’s “highest re-plan risk” (AudioCapture races) did not blow up the project. What *did* hurt was **legacy string parity** and **who loads Speaker when** — contract details at the CLI seam, not topology math.

### Qt integration: callbacks in, signals out

Worker threads must not touch widgets. The pattern that scales is:

1. Workers invoke plain Python callbacks (`ControllerCallbacks`).
2. A **`SignalBridge` QObject** implements those callbacks by calling `pyqtSignal.emit`.
3. Slots on `HecklerMainWindow` run on the GUI thread.

`emit` from a non-GUI thread is the supported Qt path; pytest-qt can falsify it (`test_signal_bridge_transcript_from_worker_thread`). I no longer need to choose between “queue + QTimer poll” and “subclass QThread per worker” for this codebase — **controller callbacks + bridge** keeps pipeline tests mock-friendly and GUI tests focused on threading law.

### Model load belongs off the GUI thread, full stop

~10s Whisper + ~3s Kokoro on the thread that runs `QApplication.exec()` is not a performance issue — it is a **correctness** issue (frozen UI, re-entrancy risk). `ModelLoadThread` (`QThread` calling `load_models`) is the minimum viable pattern; modal progress dialogs were rightly rejected in `gui-T3.md` because they tempt nested event loops.

### Status strings are a presentation contract, not log lines

T5’s amendment crystallized something easy to mishandle: the controller emits **semantic** progress/status (`Loading transcription model (large-v3 / CUDA)...`, `Mic open. Listening.`); the CLI prepends `[HECKLER] `; the GUI shows raw text in the status bar. Collapsing those layers in T1 (`Running in persona mode.`) broke **kill-criteria tests** that encoded user-visible behavior. Treating “what happened” separately from “how it is printed” is a reusable pattern anywhere you have CLI + GUI + future webhooks.

### Pre-plan coupling maps age; their *method* does not

The context map at scout SHA `dcc28d71` was **wrong on line numbers** after T1–T3, but **right on the failure modes** (stale Reactor ref, `is_playing` mismatch, stdout vs feed, shared Transcriber). Audit §10 marked every flagged surface **verified** against shipped code. The learning is not “scout harder once” — it is **keep the coupling tuples, refresh the citations**, and never claim “zero in-scope file changes” without `git diff <map-sha>..<execution-start>` on every §File map `direct` row.

### Green tests + audit `fail` is a coherent state

The first audit failed on **F-PROV-1** (map stale) and **F-1** (plan §0 falsely “fresh”), not on missing `PipelineController` behavior. That distinction matters for emotional calibration: the implementation lesson (“controller/GUI slice is sound”) and the process lesson (“archaeology did not close”) are **both true**.

### What came after gui-launcher (context only)

Later commits extended `load_models` with `persona_name` / `locale_override`, added `ensure_heavy_models`, speech-stack reload, and GUI locale controls — all **through the controller public API** without importing `_run_*` from the GUI. That validates the original boundary choice; it does not diminish gui-launcher’s scope, but it explains why today’s `controller.py` is larger than plan §2’s v1.1 snapshot.

---

## 3. Decisions I made and would make again

| Decision | Principle that generalizes |
|----------|---------------------------|
| **`heckler/controller.py` as shared owner** of lifecycle + `ReactorHolder` | Put integration layers where **all entry points** can import without pulling UI frameworks. |
| **Workers stay in `pipeline.py`; controller orchestrates** | One tested implementation of worker logic; avoid forked loops in the GUI package. |
| **Optional callbacks defaulting to `None`** with conditional legacy `print` in transcribe worker | Lets T1 land before T2; avoids duplicate `[TRANSCRIBE]` once CLI wires callbacks (coupling surface 8). |
| **`threading.Lock` in `ReactorHolder` always** | Prefer explicit, testable concurrency contracts over GIL assumptions. |
| **T2 HALT → T5 amendment** instead of executor “fixing tests” outside Files to touch | Contract drift between controller and legacy `main()` was real; amendment was the right escalation shape. |
| **Dedicated §2 status-string table after T5** | Literal-string kill criteria need a normative home, not tribal knowledge in `test_pipeline.py`. |
| **`heckler-gui` separate console script** | Keeps headless `heckler` import path free of PyQt6; matches “GUI is optional product surface, required dep per your packaging choice.” |
| **`pytest-qt` + `QT_QPA_PLATFORM=offscreen` in test module** | GUI regressions belong in CI-shaped tests, not manual smoke only. |
| **Required PyQt6 in runtime deps** (user decision) | Accept packaging cost up front rather than optional-extra import failures at `heckler-gui` time. |

---

## 4. Decisions I made that I would change

| Choice | Why it hurt | Better rule next time |
|--------|-------------|------------------------|
| **Plan §0 “staleness check” without diffing map SHA → execution start** | Declared map “fresh” while `pipeline.py` and `pyproject.toml` had changed — audit **F-1**, **F-PROV-1**. | After first architectural landing, **rescout or amend §0** with `git diff` output on all `direct` map paths. |
| **Leaving §8 PROVISIONAL after `56c3748e` committed T3 + plan tree** | Readers (and future you) see “Complete” beside “T3 uncommitted” — audit **F-3**. | When the provisional file list goes empty, **rewrite §8.1** in the same commit or immediate follow-up. |
| **`gui-T1.md` claiming `main()` imports `ReactorHolder` inside `main()`** | Shipped `main()` only imports `ControllerCallbacks`, `PipelineController` — audit **F-2**. | Decision logs get a **“Landed”** bullet or post-merge diff against `HEAD` before auditor handoff. |
| **No re-audit / hygiene subtask after audit `fail`** | Provenance blockers archived with the plan — downstream tasks cite gui map as **historical baseline** (locale-lang context-map already does). | Treat audit `fail` like a HALT: **T6-shaped doc fix** or rescout before archive, same as transcription-engine. |
| **Serial T3 after T2/T4 though DAG allowed parallel** | Harmless for files, but wasted wall-clock. | When `{T2,T3}` are file-disjoint, actually parallelize if agent capacity exists. |
| **Single interleaved `QPlainTextEdit` for “feeds”** | Audit **F-4** / CR-2: task prose said plural feeds; UX is one stream. | Either narrow task wording in the plan or split widgets up front if scanability matters. |
| **HALT narrative only in plan §7, not a durable `.dev/halts/` or decision-log entry** | T2→T5 story is clear *now*; loses detail if chat logs vanish. | One-file HALT summary linked from §7 when an amendment fires. |

**Underlying error (again):** conflating **implementation closure** (tests green, controller works) with **narrative closure** (maps, §8, decision logs indexable from `HEAD` without caveats).

---

## 5. Patterns in my own thinking

- **Anchored on the scariest coupling (mode teardown)** because it *felt* like replan territory — meanwhile **CLI parity** (Speaker load gate, banner strings, test file ownership) was the actual blocker. A useful heuristic: when a plan lists both “distributed teardown” and “legacy output contract,” **bet on the contract first** if tests encode user-visible strings.
- **Trusted the context map’s freshness bit** because the orchestrator had just written a careful §0 — that was **narrative confidence**, not `git` evidence. The map’s *coupling surfaces* deserved trust; its *staleness verdict* did not.
- **Under-used parallel execution** when the DAG explicitly allowed `{T2,T3}` after T5 — familiar serial “finish backend then UI” habit won over the plan.
- **Treated audit `fail` as “documentation nit”** risk because pytest was green — persona-system had already taught the archaeology lesson; gui-launcher partially re-learned it on a different artifact (scout SHA vs §8 SHA vs `c2fd91e` vs `56c3748e`).
- **Comfortable deferring E2E GUI + real CUDA** (explicit in decision logs) — correct for scope — but easy to forget that **`ModelLoadThread.run` exception → QMessageBox** still has no automated falsifier (audit CR-1). That is acceptable only if manual smoke is scheduled, not if it is forgotten entirely.

---

## 6. Open questions

- **Controller API ergonomics:** `swap_persona` when not in persona mode raises `PipelineNotRunningError` with a “requires persona mode” message (audit CR-4) — is a dedicated “invalid operation” type worth it for GUI error copy?
- **CLI vs GUI parity on reactions:** CLI `on_reaction` prints only when `spoken` is true; GUI receives all branches. Is silent discard of non-spoken reactions in the terminal intentional forever?
- **Density-gate transcripts:** T1 deferred surfacing utterances rejected before the reaction queue — does the GUI ever need “heard but ignored” visibility?
- **Install matrix:** PyQt6 + torch CUDA on clean Windows/Linux CI images — still environment-specific; when does a headless job try `pip install .` and import `PyQt6`?
- **WASAPI / `AudioCapture.stop()` hang:** accepted risk in gui-T1 — any signal in the field that 5s join is insufficient?
- **Evolution of `load_models` vs `ensure_heavy_models`:** post-launcher locale/reload work added API surface — worth a single “operator model load” diagram spanning CLI, GUI loader thread, and reload mutex?

---

## 7. Single paragraph synthesis

Gui-launcher taught that **extracting a Qt-free `PipelineController` with explicit callback and hot-swap seams turns a monolithic CLI into a family of shells**, and that **the hard part of dual UI is not drawing widgets but pinning contracts** (who loads which model, what strings mean, how worker output reaches the main thread). The work also reinforced persona-system’s archaeology lesson in a new shape: **scout coupling predictions were valuable while scout freshness claims were not**, and **T2’s HALT on legacy parity was the real integration gate — not the feared AudioCapture replan**. What I want to remember in six months: **invest in the controller boundary and status-string tables early; treat map SHA + §8 + decision logs as versioned artifacts that must move with `HEAD`; and when audit fails on provenance, fix or rescout before archive even if pytest says 66 passed.**

---

## Cross-links (for future you)

| Artifact | Path |
|----------|------|
| Methodology twin (process, HALT, closure) | `.dev/retrospectives/methodology/2026-05-23-gui-launcher.md` |
| Audit (verdict `fail`, integration scenarios) | `.dev/audits/2026-05-17-gui-launcher.md` |
| Archived plan + packets | `.dev/archive/gui-launcher/` |
| Decision logs | `.dev/decision-logs/gui-T1.md`, `gui-T3.md` |
| Design deferrals (original intent) | `.dev/persona-system.md` §GUI Surface, `.dev/transcription-engine.md` §GUI Surface |
| Initial land commits | `58b0bb76` (T1), `e5cadf8b` (T5), `bd41e55f` (T2), `56c3748e` (T3 + plan tree) |
