# Audit report — gui-launcher

## 1. Audit metadata

| Field | Value |
|-------|--------|
| **Task name** | gui-launcher (PyQt6 GUI + `PipelineController` extraction) |
| **Plan** | `.dev/plans/gui-launcher/plan.md` v1.1 |
| **Audit date** | 2026-05-17 |
| **Repository HEAD** | `56c3748e99ea84bb6fa398bbaf474e0508918a99` |
| **Working tree** | clean (`git status` at audit time) |
| **Context map** | `.dev/plans/gui-launcher/context-map.md` (present) |
| **Readiness verdict (scout)** | CONDITIONAL |
| **Phase 0 discipline** | Task statement + plan §2 (shared contracts) + code/tests read before pinning cold read; plan §0/§8 prose was partially visible in the same file read as §1–§2 — cold-read list is pinned from code-first synthesis, not from §8 narrative. |
| **Phase 4 focus (2–3 areas)** | **Integration seams** (controller ↔ `pipeline` workers ↔ GUI `SignalBridge`); **Failure paths** (callback exceptions, stop ordering, model-load thread errors); **Regression surface** (CLI `main()` delegation + legacy banner strings). Rationale: highest coupling and user-visible contracts live at these seams. |
| **Integration seams waiver** | Not waived — multiple meaningful seams exist. |
| **Re-audit** | No — first audit (`**Audit document revision:**` not applicable). |

---

## 2. Provenance log (Phase 0.5)

### Context map

- **Path:** `.dev/plans/gui-launcher/context-map.md`
- **Scout commit SHA (header):** `dcc28d71ebb140b57bdda74951f21fda75922918`
- **Audit-time HEAD:** `56c3748e99ea84bb6fa398bbaf474e0508918a99`
- **Working tree at scout time (header):** dirty — listed paths (`?? .dev/retrospectives/`, `?? next_steps.md`, `?? transcripts/a7dc8626.md`) are **out of §File map scope** per scout; no `dirty-state caveat` applies to in-scope coupling rows on those paths.

### SHA comparison (map base → HEAD)

- **Result:** **diverged** (HEAD is not the scout base commit; `dcc28d71` is an ancestor of HEAD).
- **§File map paths with content changes** between `dcc28d71..HEAD` (from `git diff --name-only dcc28d71..HEAD` scoped to §File map):

  | Path | In §File map |
  |------|----------------|
  | `heckler/pipeline.py` | direct |
  | `pyproject.toml` | direct |

- **Other §File map rows:** no blob change on that range (scout catalog still describes those files at HEAD for *content* purposes, aside from the two rows above).

### Scout grep coverage vs orchestrator §5.4 vocabulary

- The orchestrator skill describes §5.4 as **hidden-coupling tuples** with `Tn` attribution, not a separate enumerated grep vocabulary file in-repo.
- The scout’s **§Coupling surfaces** records concrete grep bullets (Reactor sites, `is_playing`, thread kwargs, CLI flags, literals, etc.).
- **Gap (minor):** the scout’s grep list does not explicitly record the post-plan console script token **`heckler-gui`** / `heckler.gui.app:main` (introduced after the scout run). Treat as **`scout-incomplete`** feedback to pre-plan-exploration, not a shipped-code defect.

### Plan-artifact provenance (`git show HEAD:<path>`)

| Artifact | Result |
|----------|--------|
| `.dev/plans/gui-launcher/plan.md` | present-in-HEAD |
| `.dev/plans/gui-launcher/packets/T1.md` … `T5.md` | present-in-HEAD |
| `.dev/decision-logs/gui-T1.md` | present-in-HEAD |
| `.dev/decision-logs/gui-T3.md` | present-in-HEAD |
| `heckler/gui/app.py` | present-in-HEAD |
| Plan §8.1 “Committed SHA” `c2fd91e49122aafeeea0fbe9f66d3cdb866c355b` | **≠** audit HEAD — closure narrative in the plan is **stale vs current HEAD** (process/documentation drift; see findings). |

### Phase 0.5 findings filed here

| ID | Type | Severity | Notes |
|----|------|----------|-------|
| **F-PROV-1** | `context-map-stale` | **major** | §File map rows `heckler/pipeline.py` and `pyproject.toml` diverged between scout SHA `dcc28d71…` and audit HEAD. Scout-derived “treat-as-prediction” claims on line-level `pipeline.py` citations in the context map are **stale-qualified**. |
| **F-PROV-2** | `scout-incomplete` | **minor** | No explicit scout grep bullet for `heckler-gui` / `heckler.gui.app:main` entry surface. |

---

## 3. Context chain completeness

| Artifact | Status | Limits |
|----------|--------|--------|
| Context map | Provided | Stale on two direct paths (F-PROV-1). |
| Orchestrator plan | Provided | §0 staleness narrative contradicts git diff vs scout SHA; §8 snapshot/SHAs partly obsolete. |
| Packets T1–T5 | In HEAD | Used for Phase 1 packet-vs-reality spot checks. |
| Decision logs gui-T1, gui-T3 | In HEAD | gui-T1 has one inaccurate sentence vs code. |
| Changelog | Not a plan §4 deliverable for T4 (README only). Optional narrative absent from chain — no `incomplete` solely for that. |
| Code + tests | Read + pytest executed | Full story available. |
| Phase 0 | Completed before detailed reconciliation with §5/§8 handoff prose | §0/§8 in same physical file as §2 — minimal priming risk; cold-read list is code-anchored. |

---

## 4. Cold-read log (Phase 0 — pinned)

Contract inputs: plan §1 task statement + §2 shared contracts (types, status strings, error envelope, naming, logging, tests, CLI surface).

| ID | Severity (guess) | Topic | Notes |
|----|------------------|-------|-------|
| **CR-1** | observation | `ModelLoadThread.run` | Marked `# pragma: no cover` — real failure paths inside `run()` rely on manual/integration confidence; tests mock `load_models` at the boundary. |
| **CR-2** | minor | GUI layout vs “feeds” wording | Task §1 asks for live transcript **and** reaction **feeds**; `HecklerMainWindow` uses a **single** `QPlainTextEdit` interleaving transcript lines and reaction lines. Functionally adequate; wording-level scope question only. |
| **CR-3** | minor | CLI `on_reaction` lambda | `pipeline.main()` wires `on_reaction` to print **only** when `spoken` is true; non-spoken outcomes are not echoed to stdout (GUI still receives `was_spoken=False` via the same callback shape). Verify this matches intended CLI UX; not a §2 literal-string violation (§2 does not mandate printing false branches). |
| **CR-4** | observation | `swap_persona` wrong-mode error type | Uses `PipelineNotRunningError` with message `swap_persona requires persona mode` when `_mode != "persona"` — semantically closer to “invalid operation” than “not running”; minor API ergonomics. |
| **CR-5** | observation | `CHANGELOG.MD` on disk | Case-sensitive path vs `CHANGELOG.md`; not in `git show HEAD:CHANGELOG.md`. Out of plan §8.2 ordered list — no merge blocker from audit chain unless release process requires it. |

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | One-line description |
|----|----------|------|-------|---------|----------------------|
| F-PROV-1 | major | `context-map-stale` | 0.5 | — | Scout base SHA predates HEAD; `pipeline.py` + `pyproject.toml` (§File map `direct`) changed since scout. |
| F-PROV-2 | minor | `scout-incomplete` | 0.5 | — | Scout grep list missing explicit `heckler-gui` entry token. |
| F-1 | major | `prediction-divergence` / process | 1 | Orchestrator | Plan §0 claims specific HEAD + “map is fresh / zero in-scope source changes” — false vs `git diff dcc28d71..HEAD` on §File map. |
| F-2 | minor | `decision-log-stale` | 3 | T1 | `gui-T1.md` states `main()` imports `ReactorHolder` inside `main()`; shipped `main()` imports `ControllerCallbacks`, `PipelineController` only. |
| F-3 | minor | `intent-drift` (doc) | 1 | Plan | Plan header + §8 still describe T3 / plan artifacts as uncommitted and record obsolete SHAs vs clean tree at `56c3748…`. |
| F-4 | minor | `intent-drift` | 1 | T3 | Single combined feed vs plural “feeds” in task statement (CR-2). |
| F-5 | observation | — | 4 | T3 | `ModelLoadThread.run` pragma no cover — acceptable with mock-based tests; document risk for manual smoke. |

---

## 6. Detailed findings (above minor)

### F-PROV-1 — `context-map-stale` (major)

- **Expected:** Context map §File map rows reflect the same blob lineage as the code under audit for `direct` paths, or the map is re-scouted with updated provenance.
- **Found:** `git diff dcc28d71ebb140b57bdda74951f21fda75922918..HEAD --name-only` within §File map includes `heckler/pipeline.py` and `pyproject.toml`.
- **Evidence:** Scout header SHA `dcc28d71…`; audit HEAD `56c3748…`; git diff scoped to map paths.
- **Caveat for downstream readers:** Any scout **line-number–pinned** `pipeline.py` references in the context map body are **stale-qualified** for coupling Surfaces 1–4, 8.

### F-1 — Plan §0 staleness narrative (major — process / prediction vs git)

- **Expected:** §0 “Staleness check” and “Current HEAD” reflect `git` reality or are explicitly framed as a point-in-time snapshot with amendment instructions.
- **Found:** §0 records `Current HEAD: 9715105…` and claims zero in-scope source file changes vs the context-map base — contradicts current repository (`56c3748…`) and the two-path diff above.
- **Evidence:** `.dev/plans/gui-launcher/plan.md` §0 lines 19–21 vs `git rev-parse HEAD` and `git diff dcc28d71..HEAD -- heckler/pipeline.py pyproject.toml`.

---

## 7. Adversarial test log (Phase 4)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| **S1 — Worker → Qt cross-thread** | `pyqtSignal.emit` from non-GUI thread delivers to GUI thread without deadlock | `test_signal_bridge_transcript_from_worker_thread` emits from a Python worker thread; `qtbot.waitUntil` observes feed text | **passes** (automated) |
| **S2 — Model load must not block `QApplication`** | `load_models` off GUI thread | `ModelLoadThread` runs `load_models` in `QThread`; test asserts call on non-main thread id | **passes** (automated) |
| **S3 — Coupling Surface 8 (stdout vs callback)** | With CLI callbacks wired, transcribe worker should not duplicate `[TRANSCRIBE]` prints | `_run_transcribe_worker` prints only when `on_transcript is None`; CLI passes non-`None` callback in `main()` | **passes** (code review) |
| **S4 — §5.4 item 3 AudioCapture / `is_playing` on mode switch** | Persona uses `speaker.is_playing`; transcribe uses bare `threading.Event()` | `PipelineController._start_persona_mode` / `_start_transcribe_mode` in `heckler/controller.py` | **passes** (code review) |
| **S5 — Transcribe isolation (`load_models(mode=…)`)** | `mode="transcribe"` skips Speaker | Implemented in `PipelineController.load_models`; falsified by tests per plan §8.3 | **passes** (automated + contract table) |
| **S6 — `ReactorHolder` hot-swap** | Reaction loop reads holder each iteration; swap under lock | `reactor_holder.get()` at loop head in `_run_reaction_worker`; `test_reactor_holder_swap_thread_safety` | **passes** (automated) |
| **S7 — `ModelLoadThread.run` exception path** | User sees critical message + `app.quit` on failure | Implemented in `app.py`; not covered by automated test | **unknown** (manual / add test if desired) |

---

## 8. Coverage gap list (Phase 5)

| Item | Severity | Notes |
|------|----------|-------|
| T1 kill (AudioCapture internal join hang / WASAPI) | minor (known risk, decision-log deferred) | No falsifying test — explicitly deferred in `gui-T1.md`. |
| T3 kill (full stack install conflict torch + PyQt6) | minor | Environment-specific; dev smoke noted in decision log, not CI matrix here. |
| `ModelLoadThread.run` exception UI path | minor | **CR-1** / **F-5** — no automated assertion of `failed` → `QMessageBox` → `quit`. |
| Flag 4 (`missing_test_coverage`) | addressed | `pytest-qt` + `tests/test_gui.py` + offscreen default in test module. |

**Kill-criterion / automated-coverage contradiction:** None identified — plan + logs explicitly defer some runtime risks without claiming pytest coverage for them.

**Test quality:** `tests/test_gui.py` asserts real behaviors (widget presence, signal delivery, off-thread emit, export URL). Not tautological.

**pytest result (audit run):** `66 passed` for `tests/test_controller.py`, `tests/test_pipeline.py`, `tests/test_gui.py` (~3.7s, `QT_QPA_PLATFORM=offscreen`).

---

## 9. Verdict

### `fail`

**Blockers (must resolve before a “merge archaeology / scout contract” bar):**

1. **F-PROV-1** — Refresh `.dev/plans/gui-launcher/context-map.md` provenance (new scout SHA) **or** formally supersede staleness in orchestrator §0 with a dated amendment that matches `git` — and update §File map line-number citations that are now wrong.
2. **F-1** — Reconcile plan §0 staleness narrative with `git` (HEAD SHA, diff vs scout base, removal of “zero in-scope changes” claim unless true).

**Non-blocking (should fix or justify):**

- **F-PROV-2**, **F-2**, **F-3**, **F-4** (minors / documentation).

Once F-PROV-1 and F-1 are addressed, a re-audit should re-run **all** phases per skill (discard prior cold read; revision banner).

---

## 10. Scout-prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| Surface 1 — reaction worker holds stale `Reactor` ref | confirmed_coupling | **verified** — addressed by `ReactorHolder` + `get()` per iteration | — |
| Surface 2 — `is_playing` wiring differs by mode | confirmed_coupling | **verified** — controller reconstructs `AudioCapture` with correct event | — |
| Surface 3 — `main()` blocks Qt if reused directly | confirmed_coupling | **verified** — GUI uses `PipelineController` + `QApplication.exec()`, not `main()` loop | — |
| Surface 4 — frozen config + workers | confirmed_coupling | **ruled-out** as GUI bug for v1 — GUI does not live-mutate `HecklerConfig` for running workers | observation |
| Surface 5 — single shared `Transcriber` | confirmed_coupling | **verified** — controller holds `_transcriber` across mode switch | — |
| Surface 6 — VAD params baked at `AudioCapture` construction | confirmed_coupling | **verified** — mode switch tears down capture + workers | — |
| Surface 7 — PyQt6 optional vs required packaging | suspected_coupling | **ruled-out** as “optional-only” — user chose **required**; `pyproject.toml` lists `PyQt6>=6.5` in runtime deps | — |
| Surface 8 — stdout vs GUI feed | confirmed_coupling | **verified** — callback + conditional print path | — |
| Flag 1 — controller location | ambiguity | **verified** — `heckler/controller.py` landed | — |
| Flag 2 — hot-swap indirection | ambiguity | **verified** — `ReactorHolder` | — |
| Flag 3 — runtime vs startup mode switch | ambiguity | **verified** — `switch_mode` implemented | — |
| Flag 4 — no PyQt6 test infra | ambiguity | **verified** — `pytest-qt` + `tests/test_gui.py` | — |
| Flag 5 — GUI imports `_run_*` | ambiguity | **verified** — GUI imports controller + widgets only | — |

---

## 11. Finding status vs prior revision

Not applicable (first audit).
