# Audit — persona-speech-reload

**Date:** 2026-05-22  
**Plan:** `persona-speech-reload` v1.1.0  
**Audit HEAD:** `a5e5b96a2420cc3eab85f12c876589e2be9a8d83` (master)  
**Plan §8.1 closure SHA:** `3122805444a99b8b555a3e65a1b500fc4480d5e4` (implementation chain; plan bundle committed in `a5e5b96a`)  
**Context map:** `.dev/plans/persona-speech-reload/context-map.md` — CONDITIONAL @ scout SHA `80c60a0ea5d1008d2c9f57d17520ada7ea9f6aac`  
**Auditor skill:** auditor-review v0.4  
**Re-audit:** No (initial cold audit)

---

## 1. Audit metadata

| Field | Value |
|-------|--------|
| Task name | persona-speech-reload |
| Plan version | 1.1.0 (status: Complete — §8 handoff emitted) |
| Context map path | `.dev/plans/persona-speech-reload/context-map.md` |
| Readiness at planning | CONDITIONAL |
| Provenance | Scout SHA **diverged** from audit HEAD (expected post T1–T8); see §2 |
| Working tree at audit | **Clean** (no dirty paths) |
| Phase 0 discipline | Cold read completed before plan prose (beyond §1–§2), packets, decision logs, CHANGELOG |
| Auditor focus areas | **Integration seams** (mandatory — context map §Coupling surfaces 1, 3, 4, 5); **Failure paths** (reload cancel/fail, `swap_persona` misuse); **Concurrency / ordering** (`_reloading` mutex, reload-before-Reactor) |
| Pytest (auditor) | `tests/test_locale.py tests/test_controller.py tests/test_gui.py tests/test_pipeline.py tests/test_speaker.py` — **167 passed**, 3.70s. Plan §8.1 claims `pytest tests/ -m "not heavy" -q` → **349 passed** (not re-verified end-to-end; full-suite run hung >3 min in this environment) |
| T7 verification command | Same subset as above (includes `test_config`, `test_persona` in packet; auditor subset omitted those two modules but core contract files covered) |

---

## 2. Provenance log (Phase 0.5)

| Check | Result |
|-------|--------|
| Context map path | Present |
| Scout SHA vs audit HEAD | **diverged** — `80c60a0` → `a5e5b96a` |
| Diverged §File map `direct` paths (implementation) | `heckler/locale.py`, `heckler/controller.py`, `heckler/gui/main_window.py`, `heckler/gui/app.py`, `heckler/pipeline.py`, `tests/test_locale.py`, `tests/test_controller.py`, `tests/test_gui.py`, `tests/test_pipeline.py` |
| Working tree at scout time | **dirty** (untracked `PERSONA_SPEECH_RELOAD.md`, `GUI_DARK_THEME.md`) |
| Working tree at audit time | **clean** |
| Scout grep coverage | No `scout-incomplete` gaps filed — coupling tuples recorded; orchestrator contract vocabulary satisfied |

### Plan-artifact provenance @ audit HEAD (`a5e5b96a`)

| Artifact | `git show HEAD:<path>` |
|----------|------------------------|
| `PERSONA_SPEECH_RELOAD.md` | present-in-HEAD |
| `.dev/plans/persona-speech-reload/context-map.md` | present-in-HEAD |
| `.dev/plans/persona-speech-reload/plan.md` | present-in-HEAD (added `a5e5b96a`) |
| `.dev/plans/persona-speech-reload/packets/T1.md` … `T8.md` | present-in-HEAD (added `a5e5b96a`) |
| `.dev/decision-logs/persona-speech-reload-T2.md` | present-in-HEAD |
| `.dev/decision-logs/persona-speech-reload-T4.md` | present-in-HEAD |
| `CHANGELOG.MD` (persona-speech-reload section) | present-in-HEAD |
| `.dev/audits/2026-05-22-locale-lang-propagation.md` (FIND-A6 addendum) | present-in-HEAD |
| `GUI_DARK_THEME.md` | present-in-HEAD (not in plan §4 scope) |

### Plan-artifact provenance @ plan §8.1 closure SHA (`31228054`)

| Artifact | Status |
|----------|--------|
| Implementation code (T1–T7) | present-in-HEAD @ `31228054` |
| `context-map.md` | present-in-HEAD |
| `plan.md`, packets T1–T8 | **absent-from-HEAD** (documented in plan §8.2; remediated in `a5e5b96a`) |
| This audit file | absent-from-HEAD (expected until audit commit) |

### Phase 0.5 findings

| ID | Severity | Type | Phase | Summary |
|----|----------|------|-------|---------|
| PSR-P01 | major | `context-map-stale` | 0.5 | Scout SHA `80c60a0` diverges from audit HEAD on all `direct` §File map implementation paths (expected after execution; stale-qualified scout predictions below) |
| PSR-P02 | observation | `artifact-not-in-HEAD` | 0.5 | §8.1 closure SHA `31228054` did not contain `plan.md`/packets; §8.2 acknowledged; fixed @ `a5e5b96a` |

---

## 3. Context chain completeness

| Artifact | Provided | Limits |
|----------|----------|--------|
| Context map | Yes | Pre-implementation SHA; coupling labels still valid |
| Plan + packets T1–T8 | Yes | |
| Binding spec `PERSONA_SPEECH_RELOAD.md` | Yes | |
| Decision logs T2, T4 | Yes | |
| Supersession banners (locale-lang T4, T7) | Yes | |
| CHANGELOG | Yes | |
| Code + tests | Yes (diff `80c60a0..HEAD`) | |
| Prior audit addendum (locale-lang FIND-A6) | Yes | |
| Pre-plan unstructured notes | Not separate from context map | Map + spec sufficient |

---

## 4. Cold-read log (Phase 0 — pinned)

| ID | Severity (guess) | Surface | Finding |
|----|------------------|---------|---------|
| CR-01 | minor | `a5e5b96a` commit | Bundles unrelated `GUI_DARK_THEME.md` (583 lines) and 13 one-line `transcripts/*.md` with plan bundle — not in subtask packets |
| CR-02 | observation | `heckler/controller.py:swap_persona` | No runtime speech-signature check; stale STT/TTS possible if caller bypasses `_apply_persona_and_speech` |
| CR-03 | observation | `heckler/gui/app.py:ModelLoadThread.run` | Always calls `locale_override_fn()` even in transcribe mode (combo hidden; low risk) |
| CR-04 | pass | `heckler/locale.py` | `speech_stack_signature` / `supported_locale_labels` present and minimal |
| CR-05 | pass | Reload API surface | `SpeechReloadPolicy`, predicate methods, `reload_speech_stack_for_persona` present |
| CR-06 | pass | GUI orchestration | `_apply_persona_and_speech`, `_ReloadThread`, `_reloading`, locale sentinel `None` for "From persona" |
| CR-07 | pass | Mandatory test removal | `test_swap_persona_does_not_change_transcriber_whisper_language` absent from `tests/` |

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| PSR-P01 | major | `context-map-stale` | 0.5 | — | Scout SHA diverged from HEAD on all direct implementation files (stale-qualified) |
| PSR-P02 | observation | `artifact-not-in-HEAD` | 0.5 | T8 | Plan/packets absent @ `31228054`; remediated @ `a5e5b96a` |
| PSR-01 | observation | `undeclared-change` | 1 | — | `GUI_DARK_THEME.md` + `transcripts/*.md` in `a5e5b96a` outside plan §4 / non-goals |
| PSR-02 | observation | `coverage-gap` | 5 | T5/T7 | Spec §20 S1–S3 (real Whisper/Kokoro boot) remain manual; acknowledged in CHANGELOG |
| PSR-03 | minor | `coverage-gap` | 5 | T5 | No test that locale-combo change **while running** (without persona change) triggers `_apply_persona_and_speech`; CHANGELOG defers |
| PSR-04 | observation | `adversarial-fail` | 4 | T2 | Direct `swap_persona` after cross-locale load leaves English Transcriber — **by contract** (caller must guarantee signature); GUI path guarded |
| PSR-05 | observation | — | 1 | — | Intent traceability: task statement → plan → code **aligned** on conditional reload, locale combo, F1/F2 fixes |
| PSR-06 | observation | — | 2 | T1–T2 | Shared contract symbols, log literals, and round-trip tests **match** §2 |
| PSR-07 | observation | — | 3 | T2/T4 | Decision logs match landed callable/reload split; locale-lang logs **banner-superseded** |

No `critical`, `contract-violation`, `intent-drift`, `narrative-concealment`, or `process-violation` findings at audit HEAD.

---

## 6. Detailed findings (above minor)

### PSR-P01 — `context-map-stale` (major, stale-qualified)

**Expected:** Context map reflects pre-implementation tree @ `80c60a0`.  
**Found:** All `direct` implementation paths in §File map changed in `80c60a0..a5e5b96a`.  
**Evidence:** `git diff 80c60a0..HEAD --stat` on `heckler/locale.py`, `controller.py`, `gui/*`, `pipeline.py`, test files.  
**Caveat:** Scout predictions (F1 combo-at-init, F2 pre-Start disable, old swap test) describe **pre-fix** state; reconciliation table marks outcomes. Not a code defect.

### PSR-P02 — Plan bundle absent @ §8.1 SHA (observation)

**Expected:** §8 closure archaeology includes plan + packets.  
**Found:** `git show 31228054:.dev/plans/persona-speech-reload/plan.md` fails; only `context-map.md` in tree. Plan §8.2 explicitly flagged **absent-from-HEAD**; commit `a5e5b96a` adds plan + packets + transcripts.  
**Action:** None at HEAD for implementation; archaeology parity achieved @ `a5e5b96a`.

---

## 7. Intent traceability (Phase 1)

| Layer | Verdict |
|-------|---------|
| Task statement → plan §1 | Faithful — reload predicate, locale combo, unified apply, CLI parity, non-goals listed |
| Plan → subtasks T1–T8 | Each scope component mapped; DAG respected |
| Subtask packets → diff | Core files match packet `files-to-touch`; extra files = plan bundle + hygiene (PSR-01) |
| Non-goals | **Respected** in code (no QSettings, no new locales, no in-place transcriber swap). **Exception:** `GUI_DARK_THEME.md` committed (doc-only, non-goal theme work) |
| Narrative vs cold read | No concealment — CHANGELOG documents deferred adversarial items matching CR-02/CR-03 class risks |
| Map → plan §4 | Scout `direct` files all in plan §4 |
| Interface inventory | `speech_stack_signature`, reload API, `swap_persona` semantics updated as scout `suspect_modified` predicted |
| Prior reasoning | locale-lang T4/T7 superseded with banners; T1 locale module unchanged per plan §0 |

---

## 8. Contract compliance (Phase 2)

| Contract area | Status | Notes |
|---------------|--------|-------|
| Types / interfaces (§2 table) | **Pass** | All named symbols exist at declared paths with signatures per grep/read |
| `locale_override` sentinel | **Pass** | `selected_locale_override()` returns `None` for "From persona"; `test_target_speech_config_empty_locale_override_ignored` |
| `swap_persona` contract | **Pass** | Docstring + Reactor-only body; cross-locale via GUI apply |
| Error envelope | **Pass** | Cancel/failure revert tests; `UnsupportedLocaleError` not fed display strings |
| Logging literals | **Pass** | INFO/WARNING patterns byte-match §2 in `controller.py` / `main_window.py` |
| Mandatory test replacement | **Pass** | Old test absent; `test_speech_stack_swap_matrix_same_sig`, `test_speech_stack_cross_locale_reload_s2` |
| CLI surface | **Pass** | No new flags; `ensure_heavy_models` in `pipeline.py:374-380` |
| Typed admission | **Pass** | `SpeechReloadPolicy` enum + `test_speech_reload_policy_values`; no getattr-only policy |

---

## 9. Decision log audit (Phase 3)

| Log | Verdict |
|-----|---------|
| `persona-speech-reload-T2.md` | **Pass** — conditional signature reload + GUI dispatch split matches code |
| `persona-speech-reload-T4.md` | **Pass** — callable snapshots at `run()` match `ModelLoadThread` + F1 test |
| `locale-lang-propagation-T4.md` | **Pass** — top banner supersedes stale "swap never rebuilds" body |
| `locale-lang-propagation-T7.md` | **Pass** — top banner supersedes init-time `config.persona_name` body |

---

## 10. Adversarial test log (Phase 4)

### Integration seams (from §Coupling surfaces)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Surface 1 — STT/TTS tuple mismatch load vs start | `target_speech_config` / reload when signatures differ | `heavy_models_need_reload`, `ensure_heavy_models` on Start; `test_target_speech_config_consistent_with_load_models`, S1/S6 GUI tests | **passes** |
| Surface 3 — `swap_persona` Reactor-only | Same signature → no Transcriber rebuild | `swap_persona` only swaps `ReactorHolder`; matrix + S2 cross-locale reload test | **passes** |
| Surface 4 — persona combo only while running (pre-fix) | Combo enabled when models ready, not only while running | `_persona_combo.setEnabled(ready and persona_mode and not reloading)` | **passes** (scout prediction was pre-fix gap) |
| Surface 5 — TOML locale merge path | Same merge as `target_speech_config` | `apply_persona_overrides` in `target_speech_config` | **passes** |
| Surface 6 — worker cfg staleness (suspected) | Disproven via shared target path | Plan §0 + T2 decision: shared `target_speech_config` | **ruled out** |
| Surface 8 — old swap test | Removed | grep: test absent | **passes** |
| Surface 9 — voice/lang prefix (suspected) | Non-blocking warning | `_check_voice_locale_warning` + `test_voice_locale_mismatch_warning_logged` | **passes** |

### Failure paths

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Ask cancel (S3 / G10) | Revert combos; no swap/reload | `test_apply_persona_and_speech_ask_cancel_reverts` | **passes** |
| Reload failure (S10 / G9) | Revert combos; clear `_reloading` | `test_apply_persona_and_speech_reload_failure_reverts`, `test_reloading_flag_cleared_on_all_paths` | **passes** |
| `swap_persona` cross-locale without reload | Caller must not do this | No guard in `swap_persona`; GUI always checks `heavy_models_need_reload` first | **passes** (contract) / **unknown** for hypothetical direct API misuse |

### Concurrency / ordering

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Reload before Reactor swap (§18.1) | Predicate before `swap_persona` | `_apply_persona_and_speech` returns early on reload path before swap branch | **passes** |
| Mutex during reload (S11/G8) | Block second change | `_reloading` disables combos; `test_reloading_disables_persona_combo_s11` | **passes** |
| FIND-A6 cross-locale hot-swap | Reload required | `test_speech_stack_cross_locale_reload_s2`, GUI cross-sig tests | **passes** |

---

## 11. Coverage gap list (Phase 5)

| Priority | Gap | Kill criterion / spec | Mitigation |
|----------|-----|----------------------|------------|
| High (accepted) | S1–S3 real model boot | Spec §20 manual | CHANGELOG + T7 packet explicit deferral |
| Medium | Locale combo change while running (persona unchanged) | T5 CHANGELOG deferral | `blockSignals` on persona path only tested |
| Low | `swap_persona` signature enforcement at runtime | Contract: caller guarantees | Documented in README + docstrings |
| Low | Full `pytest tests/ -m "not heavy"` count | Plan §8.1 | Subset 167 passed; plan claim 349 not re-run to completion here |

Scenario matrix naming: S3/S10 covered by `test_apply_persona_and_speech_ask_cancel_reverts` / `reload_failure_reverts` (not `_s3`/`_s10` suffixes) — behavior covered.

---

## 12. Scout-prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| F1 ModelLoadThread reads config at init, not combo | ambiguity Flag 1 / F1 | **verified** fixed | Callable pattern T4 |
| swap_persona Reactor-only vs heavy models | coupling Surface 3 | **verified** amended | Conditional reload via apply path |
| Persona combo enabled only while running | coupling Surface 4 | **verified** fixed | F2 removed `is_running` gate |
| TOML locale → same merge path | coupling Surface 5 | **verified** | `target_speech_config` |
| Worker cfg vs Transcriber bake | coupling Surface 6 suspected | **ruled-out** | Shared target path |
| README swap never rebuilds | coupling Surface 7 | **verified** fixed | README conditional reload table |
| Old swap test encodes wrong contract | coupling Surface 8 | **verified** removed | G6 |
| Voice prefix mismatch | coupling Surface 9 suspected | **verified** | Warning only |
| ModelLoadThread window ownership | ambiguity Flag 1 | **verified** | Callable snapshots |
| swap vs reload vocabulary | ambiguity Flag 2 | **verified** | Split `swap_persona` / `_apply_persona_and_speech` |
| Missing tests for new symbols | ambiguity Flag 3 | **verified** | T7 matrix |
| "From persona" sentinel | ambiguity Flag 5 | **verified** | `None` sentinel + tests |

---

## 13. Verdict

**`pass-with-conditions`**

Implementation matches intent and shared contracts at HEAD `a5e5b96a`. Conditional speech-stack reload, GUI locale override, unified apply path, CLI `ensure_heavy_models`, and FIND-A6 remediation are **landed and tested** at mock level. No critical or major **code** defects.

**Conditions (non-blocking):**

1. Treat S1–S3 as **manual** acceptance before declaring operator-ready Spanish boot (per spec §20; already documented).
2. Optional follow-up: test locale-combo-only change while pipeline running (PSR-03).
3. Consider moving `GUI_DARK_THEME.md` / transcript stubs off the feature archaeology commit for cleaner history (PSR-01).
4. Re-run `pytest tests/ -m "not heavy" -q` locally to confirm §8.1 **349 passed** if CI is not authoritative.

**Merge recommendation:** Safe to merge on code/test grounds; manual S1–S3 smoke remains the operator gate.

---

## 14. Implementation chain (reference)

`ae491c43` T1 → `87549218` T2 → `4b149019` T3 → `c1861894` T4 → `964f020c` T5 → `78c945bf` T6 → `2d924cdc` T7 → `31228054` T8 → `a5e5b96a` plan bundle + transcripts
