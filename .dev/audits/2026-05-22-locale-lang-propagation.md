# Audit — locale-lang-propagation

**Document index:** Revision **2** (active re-audit) · Revision **1** (historical — frozen below, do not edit)

---

# Revision 2 — Re-audit (post-amendment T6–T8)

**Audit document revision:** 2  
**Supersedes:** revision 1 verdict and finding dispositions only; revision 1 body preserved unchanged below  
**Date:** 2026-05-22  
**Plan:** `locale-lang-propagation` v1.2.0 @ `24ca9bd8` (v1.3.0 handoff prose on working tree, unstaged)  
**Prior audit:** revision 1 — verdict **`fail`** @ `d0ce6d0`  
**Auditor focus areas:** Integration seams (entry-point `load_models` / audit A4–A5), failure paths, typed-config admission — same profile as rev 1  
**Context map:** `.dev/plans/locale-lang-propagation/context-map.md` — CONDITIONAL @ scout SHA  
**Audit HEAD:** `24ca9bd8585a2b7952f5352117d0ba5cc39ba1a9` (plan §8.1 handoff SHA)  
**Working tree at audit:** `M .dev/plans/locale-lang-propagation/plan.md` (v1.3.0 §8.1 SHA align vs committed v1.2.0); audit file untracked; unrelated `transcripts/*.md`

### Omission-free artifact checklist (re-pass)

| Surface | Opened in re-pass |
|---------|-------------------|
| Plan §0–§8, §7 T6–T8 | Yes |
| Packets T1–T8 | Yes |
| Decision logs T1, T4, T7 | Yes |
| CHANGELOG locale section | Yes |
| `heckler/pipeline.py`, `heckler/gui/app.py`, `heckler/controller.py`, `heckler/locale.py`, `heckler/config.py` | Yes |
| `tests/test_pipeline.py`, `tests/test_gui.py`, contract suite | Yes |
| Prior audit rev 1 | Yes (reconciled in §14) |

---

## 1. Audit metadata (revision 2)

| Field | Value |
|-------|--------|
| Amendment chain | `4739b325` T6 → `344ca19d` T7 → `03c779e7` T8 → `24ca9bd8` (§8.1 SHA align) |
| Phase 0 discipline | Fresh cold read @ `24ca9bd8` before packets T6–T8, plan §8.6, T7 log, rev 1 narrative |
| `pytest tests/test_locale.py tests/test_config.py tests/test_speaker.py tests/test_persona.py tests/test_controller.py tests/test_pipeline.py tests/test_gui.py -q` | **146 passed**, 4.82s (auditor re-run 2026-05-22) |

---

## 2. Provenance log (Phase 0.5)

| Check | Result |
|-------|--------|
| Context map path | Present — scout SHA `56c3748` vs audit `24ca9bd8` **diverged** (expected post T1–T8) |
| Plan-artifact @ `24ca9bd8` | context-map, plan v1.2.0 §8, packets T1–T8, decision logs T1/T4/T7, CHANGELOG — **present-in-HEAD** |
| Plan v1.3.0 on disk | **on-disk-only** vs `24ca9bd8` — §8.1 handoff SHA / chain prose bump (observation R2-01) |
| Audit file @ `24ca9bd8` | **absent-from-HEAD** — untracked; plan §8.2 documents this (observation R2-02) |
| Closure SHA | `git rev-parse HEAD` = `24ca9bd8` — matches plan §8.1 @ committed v1.2.0 |

**Findings filed in Phase 0.5 (revision 2 only)**

| ID | Severity | Type | Summary |
|----|----------|------|---------|
| R2-01 | observation | `artifact-not-in-HEAD` | Working-tree `plan.md` v1.3.0 differs from `24ca9bd8` v1.2.0 (SHA-align prose only) |
| R2-02 | observation | `artifact-not-in-HEAD` | This audit file not in closure SHA (rev 1 also untracked; expected until commit) |

No new **major** provenance findings.

---

## 3. Context chain completeness (revision 2)

| Artifact | Provided |
|----------|----------|
| Context map | Yes |
| Plan + packets T1–T8 | Yes |
| Decision logs T1, T4, T7 | Yes |
| CHANGELOG | Yes |
| Code + tests (T6/T7 surfaces) | Yes |
| Prior audit rev 1 | Yes — frozen below |
| Amendment remediation map (plan §8.6) | Yes |

---

## 4. Cold-read log (Phase 0 — pinned, revision 2)

| ID | Severity (guess) | File / surface | Finding |
|----|------------------|----------------|---------|
| CR2-01 | — (pass) | `heckler/pipeline.py:374-377` | `load_models(..., persona_name=persona_name if mode == "persona" else None)` aligns with `start()` |
| CR2-02 | — (pass) | `heckler/gui/app.py:38-44` | `ModelLoadThread` passes `mode` + `persona_name` from `HecklerConfig` at load |
| CR2-03 | — (pass) | `heckler/locale.py`, `config.py` | Fail-fast locale; no silent English fallback |
| CR2-04 | — (pass) | `tests/test_pipeline.py` | `test_main_load_models_persona_name_on_persona_mode`, transcribe omits `persona_name` |
| CR2-05 | — (pass) | `tests/test_gui.py` | `test_model_load_thread_*` assert `load_models` kwargs |
| CR2-06 | observation | `plan.md` working tree | v1.3.0 unstaged vs committed v1.2.0 @ `24ca9bd8` |
| CR2-07 | observation | `prompts/**` | Still no shipped `[voice].locale` (latent until operator edits) |

Rev 1 cold-read issues CR-01/02/06 are **not reproduced** on current code @ `24ca9bd8`.

---

## 5. Findings table (revision 2)

| ID | Severity | Type | Phase | Subtask | One-line description |
|----|----------|------|-------|---------|----------------------|
| R2-01 | observation | `artifact-not-in-HEAD` | 0.5 | T8 | Plan v1.3.0 §8.1 on disk; `24ca9bd8` has v1.2.0 |
| R2-02 | observation | `artifact-not-in-HEAD` | 0.5 | — | Audit markdown not in git @ handoff SHA |
| — | — | — | — | — | *No new major/critical findings* |

Accepted carry-forward (unchanged): rev 1 **FIND-07/08/09** (minor, deferred); **FIND-01/10/11** (scout staleness / inventory — informational).

---

## 6. Detailed findings (revision 2)

### R2-01 — Plan v1.3.0 handoff prose unstaged (observation)

**Found:** `git diff 24ca9bd8 -- plan.md` updates version banner, §8.1 handoff SHA to `24ca9bd8`, and §8.2–§8.6 tables. Substance matches remediation; only archaeology drift between closure commit and working tree.

**Action:** Commit plan v1.3.0 when convenient — non-blocking for merge @ `24ca9bd8`.

### R2-02 — Audit file untracked (observation)

Plan §8.2 notes audit rev 1 **not in SHA**. Revision 2 adds this file; tracking in git improves downstream cross-reference (optional hygiene).

---

## 7. Adversarial test log (Phase 4, revision 2)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| **A1–A3** | (unchanged) | Contract tests | **passes** |
| **A4** CLI: persona-mode `main()` forwards `persona_name` to `load_models` | Same value as `start()` | `test_main_load_models_persona_name_on_persona_mode`, `test_main_load_models_uses_config_persona_when_cli_omitted` | **passes** (was **fail** rev 1) |
| **A4b** Transcribe mode omits `persona_name` | `persona_name=None` | `test_main_transcribe_load_models_omits_persona_name` | **passes** |
| **A5** GUI: `ModelLoadThread` passes `persona_name` in persona mode | kwargs at load | `test_model_load_thread_invokes_load_models_off_thread` | **passes** (was **fail** rev 1) |
| **A5b** GUI transcribe omits `persona_name` | `None` | `test_model_load_thread_transcribe_mode_omits_persona_name` | **passes** |
| **A6–A8** | (unchanged) | Controller / speaker tests | **passes** |

**Integration seams:** Surface 1 closed at CLI/GUI call sites when `persona_name` is supplied at load; controller bake unchanged and covered by T4 + entry-point tests.

**Residual (documented, non-blocking):** T7 log — no GUI integration test with real `locale=es` TOML at startup (kwargs-only); persona combo change while running still does not reload STT/TTS (Flag 2 / plan non-goal).

---

## 8. Coverage gap list (Phase 5, revision 2)

| Priority | Gap | Status |
|----------|-----|--------|
| ~~P0 CLI A4~~ | ~~`load_models` without `persona_name`~~ | **Closed** — T6 tests |
| ~~P0 GUI A5~~ | ~~GUI load omission~~ | **Closed** — T7 tests |
| P1 | `WHISPER_LANGUAGE` env ignored | Accepted deferral (FIND-07) |
| P1 | Second `load_models` replaces transcriber | Accepted deferral (FIND-08) |
| P2 | README vs `SUPPORTED_LOCALES` pytest sync | Accepted deferral (FIND-09) |
| P2 | GUI real TOML `locale=es` at startup | T7 deferred — controller bake tested elsewhere |
| P2 | `tests/test_models.py` field inventory | Observation |

---

## 9. Phase 1–3 summaries (revision 2)

- **Intent:** T6/T7 complete persona-locale propagation on default CLI/GUI paths; §8.4 Surface 1 disposition now matches code (remediates FIND-06).
- **Contracts:** §2 entry-point rows + original types/env/speaker/persona/controller — **pass** end-to-end @ `24ca9bd8`.
- **Decision logs:** T7 landed; T1/T4 deferred items unchanged; no stale prose detected.

---

## 10. Scout-prediction reconciliation (revision 2)

| Scout prediction | Outcome (rev 2) |
|------------------|-----------------|
| Surface 1 (base vs merged cfg) | **verified** closed — T6/T7 + tests |
| Surfaces 2–5, Flags 1–4 | **verified** (unchanged from rev 1) |
| `test_controller` swap hides config | **ruled out** |
| `prompts/heckler` lacks locale | **verified** informational |

---

## 11. Verdict (revision 2)

**`pass`** — merge-ready @ **`24ca9bd8585a2b7952f5352117d0ba5cc39ba1a9`**.

All revision 1 **major** findings (**FIND-02** through **FIND-06**) are **resolved** by T6–T8 and re-verified. Remaining items are accepted deferrals (FIND-07/08/09), scout staleness (FIND-01 → treat-as-prediction), or documentation hygiene (R2-01, R2-02).

**Optional hygiene (non-blocking):** `git add` audit file + commit plan v1.3.0 so disk matches §8.1 narrative.

---

## 12. Finding status vs prior revision (revision 1 → 2)

| Prior ID | Prior severity | Prior type | Status | Evidence @ `24ca9bd8` |
|----------|----------------|------------|--------|----------------------|
| FIND-01 | major | `context-map-stale` | **superseded** | Expected post-implementation; coupling types still valid — downgrade to informational |
| FIND-02 | major | `artifact-not-in-HEAD` | **resolved** | `git show 24ca9bd8:.../plan.md` has §8.1–§8.6 (v1.2.0) |
| FIND-03 | major | `process-violation` | **resolved** | §8.1 @ `24ca9bd8` accurate for closure; v1.3.0 bump is post-closure (R2-01) |
| FIND-04 | major | `adversarial-fail` | **resolved** | `pipeline.py:377`; T6 tests A4/A4b |
| FIND-05 | major | `adversarial-fail` | **resolved** | `gui/app.py:40-44`; T7 tests A5/A5b |
| FIND-06 | major | `narrative-concealment` | **resolved** | Plan §8.4 Surface 1 + §8.6 map FIND-04/05/06 closed |
| FIND-07 | minor | `coverage-gap` | **open** (accepted) | T1 decision log deferral |
| FIND-08 | minor | `coverage-gap` | **open** (accepted) | T4 decision log deferral |
| FIND-09 | minor | `coverage-gap` | **open** (accepted) | CHANGELOG deferral |
| FIND-10 | observation | `prediction-divergence` | **open** (accepted) | New module expected |
| FIND-11 | observation | `scout-incomplete` | **open** (accepted) | Pre-implementation inventory |

---

<hr />

<p align="center"><strong>— Revision 1 below is historical and frozen — do not edit —</strong></p>

---

# Revision 1 — Historical (frozen)

**Audit document revision:** 1 (initial)  
**Date:** 2026-05-22  
**Plan:** `locale-lang-propagation` v1.1.0 (working tree) / v1.0 draft §8 (`HEAD`)  
**Auditor focus areas:** Integration seams (§Coupling surfaces / entry-point `load_models` call order), failure paths (`UnsupportedLocaleError` at config construction), typed-config admission (`HECKLER_LOCALE` three-leg check)  
**Context map:** `.dev/plans/locale-lang-propagation/context-map.md` — readiness **CONDITIONAL** at planning time  
**Audit HEAD:** `d0ce6d0ee22b83aa988c1bfbeca2b5d5fffc38f8` (matches plan §8.1 handoff SHA)  
**Working tree at audit:** `M .dev/plans/locale-lang-propagation/plan.md` (§8 handoff populated locally, not in `HEAD`)

---

## 1. Audit metadata

| Field | Value |
|-------|--------|
| Task | Unified `HecklerConfig.locale` → Whisper `whisper_language` + Kokoro `kokoro_lang_code`; `HECKLER_LOCALE` + persona `[voice].locale`; controller load-time bake; document hot-swap STT/TTS limitation |
| Plan version | 1.1.0 *Complete* (working tree); *Draft — §8 not populated* (`git show HEAD:.../plan.md`) |
| Scout SHA | `56c3748e99ea84bb6fa398bbaf474e0508918a99` |
| Implementation chain | `f1cb9a14` (T1) → `02f8b58a` (T2) → `680ca30e` (T3) → `093ce56f` (T4) → `d0ce6d0e` (T5) |
| Phase 0 discipline | Completed before reading context-map body (beyond provenance header), packets, decision logs, CHANGELOG, or plan §8 narrative |
| `pytest tests/test_locale.py tests/test_config.py tests/test_speaker.py tests/test_persona.py tests/test_controller.py -q` | **101 passed**, 4.02s (auditor re-run 2026-05-22) |

---

## 2. Provenance log (Phase 0.5)

| Check | Result |
|-------|--------|
| Context map path | `.dev/plans/locale-lang-propagation/context-map.md` — present |
| Scout readiness | CONDITIONAL (Flags 1–4 resolved in plan §0) |
| SHA comparison | **diverged** — scout `56c3748` vs audit HEAD `d0ce6d0` |
| Diverged §File map `direct` rows | `heckler/config.py`, `heckler/persona.py`, `heckler/speaker.py`, `heckler/controller.py`, all listed `tests/*` direct rows |
| New module (post-scout) | `heckler/locale.py`, `tests/test_locale.py` — not in scout §File map (expected) |
| Scout working tree at scout time | **dirty** — `README.md`, `heckler/gui/app.py`, `pyproject.toml` (out of locale task scope at scout time; `gui/app.py` still relevant as integration caller) |
| Scout grep coverage vs plan §5.4 | **complete** for pre-implementation patterns (`whisper_language`, `lang_code`, `os.getenv`, CLI `add_argument`, `is_playing` N/A here); `HECKLER_LOCALE` absent pre-implementation (expected) |
| Plan-artifact provenance @ `d0ce6d0` | context-map, packets T1–T5, decision logs T1/T4, CHANGELOG section — **present-in-HEAD** |
| Plan `plan.md` §8 populated handoff | **on-disk-only** — working-tree differs from `git show d0ce6d0:.../plan.md` |
| Closure SHA verification | §8.1 cites `d0ce6d0` — matches `git rev-parse HEAD`; code artifacts at SHA verified; §8 narrative body not in SHA |

**Findings filed in Phase 0.5**

| ID | Severity | Type | Phase | Summary |
|----|----------|------|-------|---------|
| FIND-01 | major | `context-map-stale` | 0.5 | Scout SHA predates T1–T5; line-level inventory on touched files is stale-qualified |
| FIND-02 | major | `artifact-not-in-HEAD` | 0.5 | Populated plan §8.1–§8.6 (v1.1.0 Complete) exists on disk but not in `d0ce6d0` |
| FIND-03 | major | `process-violation` | 0.5 | Working-tree §8.1 claims unrelated untracked transcripts only; `plan.md` is modified unstaged |

---

## 3. Context chain completeness

| Artifact | Provided | Notes |
|----------|----------|-------|
| Context map | Yes | Stale vs implementation; coupling semantics still valid |
| Plan §1–§2 (Phase 0) | Yes | Task statement + shared contracts before narrative |
| Plan §0, §3–§8 full | Yes | §8 reconciled against `HEAD` vs working tree (FIND-02/03) |
| Packets T1–T5 | Yes | |
| Decision logs T1, T4 | Yes | Architectural tier |
| CHANGELOG | Yes | `locale-lang-propagation` section @ `d0ce6d0` |
| Code + tests | Yes | Cold-read + contract verification |
| Prior audit | No | Initial audit |
| Pre-plan unstructured notes | No | Context map §Orchestrator handoff suffices |

**Limits:** Stale-qualified scout line references. Real-hardware Kokoro voice/locale pairing remains operator validation (T1 decision log). GUI/CLI reload UX not automated (documented deferral).

---

## 4. Cold-read log (Phase 0 — pinned)

| ID | Severity (guess) | File / surface | Finding |
|----|------------------|----------------|---------|
| CR-01 | major | `heckler/pipeline.py:374-383` | `load_models(..., mode=mode)` omits `persona_name`; `start(..., persona_name=...)` merges persona afterward — `Transcriber`/`Speaker` built from base `self._config` only |
| CR-02 | major | `heckler/gui/app.py:37` | `ModelLoadThread` calls `load_models(on_progress=...)` with no `persona_name`; GUI `start("persona", persona_name=combo)` cannot retroactively fix STT/TTS locale baked at load |
| CR-03 | — (pass) | `heckler/locale.py`, `heckler/config.py` | Unknown locale raises `UnsupportedLocaleError`; no silent English fallback in resolver |
| CR-04 | — (pass) | `heckler/speaker.py:35` | `KPipeline(lang_code=config.kokoro_lang_code)` — hard-coded `"a"` removed |
| CR-05 | — (pass) | `heckler/controller.py:294-299`, `107-141` | `_heavy_model_config` + `load_models(persona_name=...)` API correctly merges persona when caller supplies `persona_name` |
| CR-06 | major? | `plan.md` vs `HEAD` | §8 completion narrative on disk only; conflicts with §8.1 “clean tree” framing |
| CR-07 | observation | `prompts/**` | No shipped persona defines `[voice].locale` — persona-locale path latent until bundles edited |

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | One-line description |
|----|----------|------|-------|---------|----------------------|
| FIND-01 | major | `context-map-stale` | 0.5 | — | Scout SHA `56c3748` vs implementation `d0ce6d0` |
| FIND-02 | major | `artifact-not-in-HEAD` | 0.5 | T5 | Plan §8 auditor handoff not in closure SHA |
| FIND-03 | major | `process-violation` | 0.5 | T5 | §8.1 tree claim omits modified `plan.md` |
| FIND-04 | major | `adversarial-fail` | 4 | T4 | CLI `pipeline.py` never passes `persona_name` to `load_models` — Surface 1 open on default headless path |
| FIND-05 | major | `adversarial-fail` | 4 | T4 | GUI `app.py` same omission — persona `[voice].locale` ineffective for STT/TTS in GUI flow |
| FIND-06 | major | `narrative-concealment` | 1 | T4/T5 | Plan §8.4 marks Surface 1 **closed**; CR-01/02 show primary entry points still split |
| FIND-07 | minor | `coverage-gap` | 5 | T1 | No test that `WHISPER_LANGUAGE` env is ignored (deferred in T1 log — accepted) |
| FIND-08 | minor | `coverage-gap` | 5 | T4 | No test for second `load_models(persona_name=...)` replacing transcriber (deferred in T4 log — accepted) |
| FIND-09 | minor | `coverage-gap` | 5 | T5 | No pytest sync README locale table vs `SUPPORTED_LOCALES` (deferred in CHANGELOG — accepted) |
| FIND-10 | observation | `prediction-divergence` | 1 | T1 | `heckler/locale.py` absent from scout §File map (new module — expected) |
| FIND-11 | observation | `scout-incomplete` | 0.5 | — | Scout `HecklerConfig` inventory omits `locale` / `kokoro_lang_code` (pre-implementation) |

---

## 6. Detailed findings (above minor)

### FIND-04 — CLI entry path leaves Surface 1 open (major, `adversarial-fail`)

**Expected (plan §1, §5.4 Surface 1, T4 kill criterion 2):** When a persona bundle defines `[voice].locale`, heavy models constructed in `load_models` must use `apply_persona_overrides` so `Transcriber._config.whisper_language` and `Speaker._config.kokoro_lang_code` match the persona.

**Found:** `heckler/pipeline.py` resolves `persona_name` for `start()` only:

```374:383:heckler/pipeline.py
        controller.load_models(
            on_progress=lambda msg: print(f"[HECKLER] {msg}", flush=True),
            mode=mode,
        )
    ...
        controller.start(mode, persona_name=persona_name, session_name=session_name)
```

`_start_persona_mode` builds merged `cfg` for workers/Reactor (`controller.py:308-311`), but `Transcriber.transcribe` uses `self._config.whisper_language` frozen at `Transcriber.__init__` (`transcriber.py:67`). With `locale="es"` in persona TOML and base `locale="en"`, Whisper stays English while worker config may show Spanish — silent STT/TTS misalignment.

**Evidence:** Controller unit tests pass `persona_name` directly (`test_load_models_persona_name_bakes_spanish_locale`); default CLI path does not. README documents `load_models(persona_name=...)` but does not wire `python -m heckler` / `--persona`.

---

### FIND-05 — GUI entry path same gap (major, `adversarial-fail`)

**Expected:** T4 decision log rejected baking locale only in `_start_persona_mode` because GUI loads models before persona selection without reload.

**Found:** `heckler/gui/app.py` still calls `load_models(on_progress=on_prog)` with no `persona_name`. `main_window.py` passes `persona_name` only to `start()` / `switch_mode`, not to model load. Operators picking a Spanish persona in the combo after load get Reactor/gates from merged config but English Whisper/Kokoro unless `HECKLER_LOCALE` was set at process start.

**Note:** GUI edits were a plan non-goal for *language picker* controls, but propagation wiring at the existing load site is part of the locale task’s integration contract when persona locale is a first-class input.

---

### FIND-06 — §8.4 Surface 1 disposition overstated (major, `narrative-concealment`)

**Expected:** §8.4 should reflect residual entry-point coupling if CLI/GUI were out of scope, or disposition should be **open** until `pipeline.py` / `gui/app.py` pass `persona_name` into `load_models` (or equivalent documented amendment).

**Found:** Working-tree plan §8.4 row “Transcriber base vs merged cfg (§5.4) | **closed**” with evidence “T4 `load_models(persona_name=...)` bakes persona locale”. That closes the controller API only, not CR-01/02. Cold-read issues CR-01/02 are not acknowledged in §8.5 seeds or §8.4 disposition.

---

### FIND-02 — Plan §8 not in closure SHA (major, `artifact-not-in-HEAD`)

**Expected:** Plan §8.2 artifact chain resolvable via `git show d0ce6d0:<path>` for binding audit archive.

**Found:** At `d0ce6d0`, `plan.md` ends with `*Pending plan execution...*` placeholder. Populated §8.1–§8.6 exists only in working tree (`git diff HEAD -- plan.md` shows +99 lines). Post-merge auditors anchoring on `d0ce6d0` will not see completion evidence without this caveat.

---

### FIND-03 — §8.1 working-tree claim (major, `process-violation`)

**Expected:** §8.1 “working tree had unrelated untracked transcripts only” if stated.

**Found:** `git status` shows `M .dev/plans/locale-lang-propagation/plan.md` — in-scope plan artifact modified after T5 commit. Misstates closure hygiene for orchestrator handoff.

---

### FIND-01 — Context map stale (major, `context-map-stale`)

Scout explored `56c3748`; implementation landed five commits later on `d0ce6d0`. Findings referencing scout line numbers on `config.py`, `speaker.py`, `controller.py` are **stale-qualified**. Coupling *types* (Surfaces 1–5) remain valid; post-implementation verification used current `HEAD` code.

---

## 7. Adversarial test log (Phase 4)

**Focus rationale:** Integration seams (mandatory — §Coupling surfaces non-empty); failure paths for locale resolution; typed-config admission for `HECKLER_LOCALE`.

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| **A1** Unknown locale at `load_config()` | `UnsupportedLocaleError` before pipeline runs | `test_load_config_heckler_locale_unknown_raises` + `resolve_locale("fr")` | **passes** |
| **A2** Whitespace-only `HECKLER_LOCALE` | Fallback `en` + resolved `a`/`en` | `test_load_config_heckler_locale_whitespace_falls_back_to_en` | **passes** |
| **A3** `load_models(persona_name=...)` with persona `locale=es` | `Transcriber`/`Speaker` configs show `whisper_language=es`, `kokoro_lang_code=e` | `test_load_models_persona_name_bakes_spanish_locale` | **passes** (isolated controller test) |
| **A4** CLI-equivalent: `load_models()` then `start(persona_name=es-persona)` | STT uses Spanish when persona TOML sets `locale=es` | `load_models` uses base config; `Transcriber` keeps load-time language | **fails** (FIND-04) |
| **A5** GUI-equivalent: load at startup, start with combo persona | Same as A4 | Same split | **fails** (FIND-05) |
| **A6** `swap_persona` to Spanish persona after English load | `Transcriber._config.whisper_language` unchanged | `test_swap_persona_does_not_change_transcriber_whisper_language` | **passes** (documented limitation) |
| **A7** `Speaker` Kokoro code for `en-gb` / `es` | `lang_code` `b` / `e` | `test_init_passes_resolved_kokoro_lang_code_to_pipeline` | **passes** |
| **A8** §5.4 suspected: swap mocks hide transcriber config | Explicit `_config.whisper_language` assertion | T4 test added | **passes** (ruled out) |

---

## 8. Coverage gap list (Phase 5)

| Priority | Gap | Status |
|----------|-----|--------|
| **P0 (blocking)** | End-to-end test: `pipeline.main()`-style sequence `load_models` without `persona_name` + `start` with persona carrying `locale=es` asserts Whisper language mismatch (would fail today) | **Absent** — FIND-04 |
| **P0 (blocking)** | GUI integration or documented amendment explicitly waiving persona-locale for GUI until reload plan | **Absent** — FIND-05 |
| P1 | `WHISPER_LANGUAGE` env ignored | Deferred with T1 decision log (FIND-07 minor) |
| P1 | Second `load_models` replaces transcriber | Deferred with T4 decision log (FIND-08 minor) |
| P2 | README table drift vs `SUPPORTED_LOCALES` | Deferred with CHANGELOG (FIND-09 minor) |
| P2 | `tests/test_models.py` does not assert `locale` / `kokoro_lang_code` field presence | Observation — scout-era inventory guard incomplete |

**Kill-criterion note:** T4 kill criterion 2 (“`load_models` still always passes raw `self._config` while persona TOML defines divergent `locale`”) is **satisfied in controller implementation** when `persona_name` is passed, but **violated in production call sites** (FIND-04/05) — treat as adversarial fail, not waived.

---

## 9. Phase 1 — Intent traceability (summary)

| Check | Result |
|-------|--------|
| Task statement vs plan §1 | Aligned |
| Non-goals (GUI picker, LLM locale, swap rebuild, split knobs) | Respected in code |
| T1–T3 subtask scopes vs diff | Matched packets |
| T4 controller API vs packet | Matched |
| T5 docs / bundle | README, `.env.example`, CHANGELOG, tracked bundle @ `d0ce6d0` — OK; plan §8 body not in SHA |
| Map → plan §4 files | `heckler/locale.py` planner-added (not in scout map) |
| §8.4 Surface 1 “closed” vs cold read | **Drift** (FIND-06) |

**Intent drift:** Partial — core resolver, env knob, Speaker wire, persona merge helper, and controller bake API match intent; **default CLI/GUI paths do not complete persona-locale propagation** despite plan closure narrative.

---

## 10. Phase 2 — Contract compliance (summary)

| Contract row | Status |
|--------------|--------|
| `heckler/locale.py` types + `SUPPORTED_LOCALES` keys | **pass** |
| `HecklerConfig.locale` / `kokoro_lang_code` + `apply_resolved_locale` | **pass** |
| `HECKLER_LOCALE` admission (declare, parse, test) | **pass** — literal `HECKLER_LOCALE` byte-equal in `config.py:74`, `.env.example`, README |
| `Speaker` → `config.kokoro_lang_code` | **pass** |
| Persona `[voice].locale` → `apply_resolved_locale` after merge | **pass** in `persona.py` |
| `load_models(persona_name=...)` | **pass** in controller; **fail** at CLI/GUI callers (FIND-04/05) |
| `swap_persona` no STT/TTS rebuild | **pass** |
| Error envelope `UnsupportedLocaleError` | **pass** |
| CLI surface N/A | **pass** |
| Logging N/A | **pass** |

---

## 11. Phase 3 — Decision log audit (summary)

| Log | Chosen approach implemented? | Stale prose? |
|-----|------------------------------|--------------|
| T1 | Yes — unified knob, no silent fallback | No |
| T4 | Yes for controller; **callers omit `persona_name`** | No stale body; assumption “operators must call `load_models(persona_name=...)`” not enforced in `pipeline.py` |

Deferred items in logs match FIND-07/08/09 and are consistently documented.

---

## 12. Scout-prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| Surface 1: Transcriber uses base config while workers get merged cfg | confirmed coupling | **prediction-divergence** at CLI/GUI — API fixed, callers not wired | FIND-04, FIND-05 |
| Surface 2: Speaker hard-coded `lang_code="a"` | confirmed | **verified** | — |
| Surface 3: `load_config` skips language | confirmed | **verified** closed | — |
| Surface 4: Whisper ISO vs Kokoro letter without mapping | suspected | **verified** ruled out via `locale.py` | — |
| Surface 5: `swap_persona` Reactor-only | confirmed | **verified** | — |
| Flag 1 unified knob | ambiguity | **verified** | — |
| Flag 2 persona hot-swap | ambiguity | **verified** (documented + tested) | — |
| Flag 3 LLM register | ambiguity | **verified** non-goal honored | — |
| Flag 4 env wiring | ambiguity | **verified** | — |
| `test_controller` mocks hide transcriber config | suspected (§5.4) | **ruled out** | — |
| `prompts/heckler` lacks locale | informational | **verified** (no locale keys in `prompts/`) | CR-07 |
| README English-only | informational | **verified** closed in T5 | — |

---

## 13. Verdict

**`fail`** — critical/major blockers:

1. **FIND-04 / FIND-05** — Primary CLI and GUI entry paths do not pass `persona_name` into `load_models`, so persona `[voice].locale` does not propagate to STT/TTS despite controller support and §8.4 “closed” claim.
2. **FIND-02 / FIND-03** — Auditor handoff §8 not in closure SHA; working-tree state misreported.

**Merge recommendation:** Amend with a small follow-up (wire `persona_name` into `pipeline.py` `load_models` and GUI reload path, plus an integration test mirroring A4) **or** plan amendment explicitly deferring persona-locale to `HECKLER_LOCALE`-only for v1 with §8.4 disposition corrected. Commit populated `plan.md` §8 or fold into the amendment commit.

**Strengths (non-blocking):** Resolver module, fail-fast errors, env semantics, Speaker parametrization, persona merge + controller bake tests, hot-swap falsifier, and operator docs are solid within isolated surfaces.

---

## 14. Finding status vs prior revision

N/A — initial audit (revision 1).
