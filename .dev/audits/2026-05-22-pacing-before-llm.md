# Audit report — pacing-before-llm

**Audit document revision:** 1 (initial)  
**Date:** 2026-05-22  
**Auditor skill:** auditor-review v0.4  
**Plan:** `.dev/plans/pacing-before-llm/plan.md` v1.0  
**Handoff tree SHA (code):** `692dfa0c9a398544b611d1d59b7609f8e0609261`  
**Audit HEAD:** `692dfa0c9a398544b611d1d59b7609f8e0609261` (matches code handoff; plan §8 handoff body is **not** in this commit — see F-002)

---

## 1. Audit metadata

| Field | Value |
|-------|--------|
| **Task name** | pacing-before-llm |
| **Plan version** | 1.0 |
| **Context map** | `.dev/plans/pacing-before-llm/context-map.md` — readiness **CONDITIONAL** at scout time |
| **Focus areas** | **Integration seams** (required): `cooldown_status` → `_run_reaction_worker` → `HeckleEvent` / `event_store` / `on_reaction`. **Concurrency / ordering**: pre-check vs post-LLM `evaluate` on one worker. **Edge cases**: score override only on post-LLM path; tri-state `passed_pacing_gate`. |
| **Phase 0 discipline** | Completed before reading decision logs, changelog, or plan prose beyond §1 task statement + §2 contracts. |
| **Re-audit** | No prior audit for this task. |

---

## 2. Provenance log

| Check | Result |
|-------|--------|
| **Context map path** | `.dev/plans/pacing-before-llm/context-map.md` |
| **Scout SHA** | `58f10f132078691a70cc0ae70a5304816fce1f25` |
| **Audit HEAD SHA** | `692dfa0c9a398544b611d1d59b7609f8e0609261` |
| **SHA comparison** | **diverged** — all `direct` §File map code paths changed since scout (expected implementation) |
| **Scout working tree** | **clean** at scout time |
| **Audit working tree** | **dirty** for plan artifacts: `M .dev/plans/pacing-before-llm/plan.md`, `D .dev/plans/_pending/pacing-before-llm/context-map.md` (plus unrelated repo changes outside this plan) |
| **Scout grep coverage** | No gaps vs plan §5.4 vocabulary — patterns in §Coupling surfaces cover `pacing_gate`, `evaluate`, `passed_pacing_gate`, `on_reaction`, `record_output`, config aliases |
| **Closure SHA (plan §8, on-disk only)** | Claims `692dfa0c` — **code at that SHA matches**; **full §8 handoff body is not in `692dfa0c:plan.md`** (placeholder only) |

### Plan-artifact provenance (`git show HEAD:<path>`)

| Artifact | HEAD @ `692dfa0c` | On disk (audit time) |
|----------|-------------------|----------------------|
| `.dev/plans/pacing-before-llm/context-map.md` | present-in-HEAD | present |
| `.dev/plans/pacing-before-llm/plan.md` | present-in-HEAD (**§8 stub only**) | present (**§8 full handoff unstaged**) |
| `.dev/plans/pacing-before-llm/packets/T1.md` … `T4.md` | present-in-HEAD | present |
| `.dev/decision-logs/pacing-before-llm-T1.md` | present-in-HEAD | present |
| `.dev/decision-logs/pacing-before-llm-T2.md` | present-in-HEAD | present |
| `.dev/eval-strategy.md` | present-in-HEAD (§4 cohort split) | present |
| `CHANGELOG.MD` (pacing section) | present-in-HEAD | present |
| `README.md` (pacing bullets) | present-in-HEAD | present |
| `.dev/plans/_pending/pacing-before-llm/context-map.md` | present-in-HEAD | **deleted** in working tree (unstaged) |

---

## 3. Context chain completeness

| Artifact | Provided | Notes |
|----------|----------|-------|
| Context map | Yes | Stale vs implementation SHA; still valid for intent/couplings |
| Plan §1–§2 (Phase 0) | Yes | §2 contracts used in cold read |
| Plan §3–§8 (post–Phase 0) | Yes | §8 complete body read from **working tree**; HEAD has stub |
| Packets T1–T4 | Yes | |
| Decision logs T1, T2 | Yes | |
| Changelog | Yes | |
| Code / tests | Yes | Inspected at `692dfa0c`; pytest re-run |
| gui-T1 decision log | Referenced in plan §8.2 | Not fully re-read (callback rule cross-checked via T2 log + code) |

**Limitation:** Findings tied to scout line numbers on `pipeline.py` / `pacing_gate.py` are **stale-qualified** — post-scout line numbers shifted after pre-LLM branch insert.

---

## 4. Cold-read log (Phase 0 — pinned)

| ID | Severity (guess) | Path / surface | Note |
|----|------------------|----------------|------|
| CR-1 | observation | `heckler/pacing_gate.py` | `cooldown_status` + `_cooldown_state_locked` cleanly dedupe math; `evaluate` unchanged semantically |
| CR-2 | observation | `heckler/pipeline.py` L179–199 | Pre-LLM branch: no `react`, no `on_reaction`, `context_buffer.push`, tri-state event fields match §2 |
| CR-3 | observation | `tests/test_pipeline.py` | `test_reaction_worker_pre_llm_pacing_skips_react` asserts react/evaluate/on_reaction skip + push + event shape |
| CR-4 | observation | `tests/test_pacing_gate.py` | Falsifier: high score does not bypass via `cooldown_status` while `evaluate` still bypasses |
| CR-5 | question | `692dfa0c:plan.md` | §8 auditor handoff at HEAD is a one-line placeholder — completion narrative may be uncommitted |
| CR-6 | observation | Commit history | Unrelated `capture-mic-gate-during-play` commits interleaved in `25ff36f9^..HEAD` range; pacing code paths themselves are coherent |

No critical **runtime** defects surfaced in cold read.

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| F-001 | **major** | `artifact-not-in-HEAD` | 0.5 | T4 / closure | Full plan **§8 auditor handoff** and **Status: Complete** exist on disk but not in `692dfa0c` — HEAD §8 is still the “populated when Complete” stub |
| F-002 | **major** | `context-map-stale` | 0.5 | — | Scout SHA `58f10f13` ≠ audit HEAD `692dfa0c`; all direct map code files diverged (expected post-implementation) |
| F-003 | minor | `decision-log-stale` | 3 | T2 | T2 log **Items deferred** still lists controller `on_reaction` falsifiers for **T3**; T3 landed at `692dfa0c` |
| F-004 | minor | `decision-log-stale` | 3 | — | `CHANGELOG.MD` T2 bullet still says controller coverage **deferred to T3**; T3 tests shipped; no T3 changelog bullet (plan §8.4 already notes) |
| F-005 | observation | `process-violation` | 0.5 | — | `.dev/plans/_pending/pacing-before-llm/context-map.md` still tracked at HEAD; working tree deletes it unstaged — promotion hygiene only |

**No** `intent-drift`, `contract-violation`, `coverage-gap`, or `adversarial-fail` findings on code contracts at `692dfa0c`.

---

## 6. Detailed findings (above minor)

### F-001 — `artifact-not-in-HEAD` (major)

**Expected:** Plan §8 at closure SHA `692dfa0c` contains completion snapshot, artifact chain, §2 evidence, and **Status: Complete**, per on-disk plan and executor handoff intent.

**Found:** `git show 692dfa0c:.dev/plans/pacing-before-llm/plan.md` ends §8 with:

> *Populated when plan status moves to **Complete** after all subtasks land…*

Working tree adds §8.1–§8.6 and changes status to **Complete** (unstaged).

**Evidence:** `git diff HEAD -- .dev/plans/pacing-before-llm/plan.md`

**Impact:** Post-merge audit archaeology breaks — auditors following `692dfa0c` cannot read the declared handoff without the working tree.

**Remediation:** Commit the on-disk `plan.md` (or amend closure SHA after commit). Re-run auditor if closure SHA changes.

---

### F-002 — `context-map-stale` (major, procedural)

**Expected:** Scout map reflects pre-change codebase.

**Found:** Scout @ `58f10f13`; implementation @ `692dfa0c`. Direct files `heckler/pacing_gate.py`, `heckler/pipeline.py`, `heckler/models.py`, `tests/test_pacing_gate.py`, `tests/test_pipeline.py`, `tests/test_controller.py` all differ from scout baseline.

**Impact:** Line-level scout citations and “current state” rows describe **pre-LLM-order** behavior. Directional couplings and flags remain valid; stale-qualified for scout-prediction table.

**Remediation:** Orchestrator may re-scout; not a code defect.

---

## 7. Adversarial test log (Phase 4)

| Scenario | Expected (§2 / intent) | Actual @ `692dfa0c` | Result |
|----------|------------------------|---------------------|--------|
| Pre-LLM cooldown: skip `react`, log pacing-only event | No LLM; event shape; `push`; no `on_reaction` | `pipeline.py` L179–199; `test_reaction_worker_pre_llm_pacing_skips_react` | **passes** |
| Post-LLM: `cooldown_status` then `react` then `evaluate(score)` | Override + TTS path unchanged | L201–240+; `test_reaction_worker_pacing_gate_after_successful_react` | **passes** |
| High score during cooldown: pre-LLM vs post-LLM override | `cooldown_status` ignores threshold; `evaluate` may bypass | `test_cooldown_status_ignores_score_override_while_evaluate_bypasses` | **passes** |
| `record_output` before `speak` | Unchanged invariant | `_execute_spoken_reply` L46–47; `test_execute_spoken_reply_records_before_speak` | **passes** |
| Pre-LLM event: no `event_reactor_results` child | Insert only when `reactor_result` set | `event_store.py` L319–320 guard | **passes** |
| `on_reaction` pre-LLM | Must not fire | No callback in pre-LLM branch; `test_on_reaction_not_fired_on_pre_llm_pacing` | **passes** |
| `on_reaction` post-LLM pacing reject | Fire with `was_spoken=False` | L259–263; controller test | **passes** |
| Slow LLM between `cooldown_status` and `evaluate` | Single worker serializes | Documented assumption (T2 log); no concurrent `react` | **passes** (architectural) |
| MagicMock without `cooldown_status` | Pre-LLM tests must set probe | `_reaction_worker_pacing_mock` in pipeline + controller tests | **passes** (suspected coupling ruled out) |
| Surface 7: skip `push` on pre-LLM fail | Scout suspected optional skip | `push` still runs (plan A4 intentional) | **observation** — confirmed intentional |

**pytest (plan §8.1 command, auditor re-run):** 21 passed, 0 failed (~3.6s).

---

## 8. Coverage gap list (Phase 5)

| Risk | Priority | Status |
|------|----------|--------|
| Kill: no test for skipped `react` on cooldown (Flag 4) | — | **Covered** — `test_reaction_worker_pre_llm_pacing_skips_react` |
| Kill: `evaluate` override semantics unchanged | — | **Covered** — existing `test_pacing_gate.py` + falsifier |
| Kill: `record_output` before `speak` | — | **Covered** — `test_execute_spoken_reply_records_before_speak` |
| Kill: post-LLM pacing test retained | — | **Covered** — `test_reaction_worker_pacing_gate_after_successful_react` |
| Kill: `on_reaction` without `ReactorResult` (Flag 3) | — | **Covered** — pipeline + controller tests |
| Integration: SQLite child row absent pre-LLM | low | **Not unit-tested** — guarded by `if rr is not None` in `insert_heckle_event_row`; acceptable given event shape tests |
| Doc prose sync (eval-strategy / README) | low | **No pytest** — plan/changelog defer; manual spot-check: eval-strategy §4 and README match code |
| End-to-end live cooldown under real clock | low | **unknown** — unit tests monkeypatch `time.time` only |

No **major** `coverage-gap` on plan kill criteria.

---

## 9. Intent traceability (Phase 1 — summary)

| Layer | Assessment |
|-------|------------|
| Task statement → code | **Aligned** — pre-LLM `cooldown_status`, post-LLM `evaluate`, event shape, `on_reaction` rules, non-goals respected (no echo skip, no gui edits, no new CLI) |
| Plan §4 files → diff | **Aligned** — T1–T3 code/tests; T4 docs + tracked plan dir; `models.py` comment-only |
| §2 contracts → implementation | **All rows verified** (see plan §8.3 on-disk; auditor independently confirmed) |
| Non-goals | **Respected** |
| Narrative vs cold read | **No concealment** — CR-5 (uncommitted §8) acknowledged in plan §8.4 hygiene and F-001 |
| Map → plan §4 | Scout `direct` files ⊆ plan files to touch; `cooldown_status` introduced in plan §2 (not in scout inventory — planner symbol, not scout miss) |

**Packet → diff:** T3 added tests beyond T2 packet list only in test files (expected). No undocumented production file edits for pacing scope.

---

## 10. Decision log audit (Phase 3 — summary)

| Log | Chosen approach vs code | Issues |
|-----|-------------------------|--------|
| T1 | **Matches** — `cooldown_status`, shared locked state, `evaluate` unchanged | None |
| T2 | **Matches** — ordering, event shape, no pre-LLM `on_reaction`, `push` on pre-LLM fail | F-003 deferred T3 line stale |

---

## 11. Scout-prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| Surface 1: `evaluate` needs score for override | confirmed coupling | **verified** — override only in `evaluate` after `react` | — |
| Surface 2: `record_output` before `speak` | confirmed | **verified** | — |
| Surface 3: post-LLM pacing event has full `reactor_result` | confirmed | **verified** — post-LLM branch unchanged | — |
| Surface 4: `passed_pacing_gate` None when score gate fails | confirmed | **verified** — pre-LLM uses `False`, not `None` | — |
| Surface 5: `on_reaction` needs `ReactorResult` on pacing reject | confirmed | **verified** — split pre/post behavior | — |
| Surface 6: config aliases | confirmed | **not-tested** (unchanged wiring) | observation |
| Surface 7: `push` after pacing reject | suspected | **verified intentional** — still pushes pre-LLM (A4) | — |
| Flag 1: score override pre-LLM | ambiguity | **resolved** — dropped on pre-LLM path (plan §0) | — |
| Flag 2: HeckleEvent shape pre-LLM | ambiguity | **resolved** — implemented per §2 | — |
| Flag 3: `on_reaction` when LLM skipped | ambiguity | **resolved** — not fired | — |
| Flag 4: missing pre-LLM test | ambiguity | **resolved** — T3 tests | — |
| Flag 5: echo skip same work item | ambiguity | **resolved** — pacing-only (deferred echo) | — |
| Inventory: `cooldown_status` | — | **prediction-divergence** (scout pre-image) | observation — planner-added API per plan §2 |

---

## 12. Verdict

### `fail`

**Blocking (must fix before merge as an auditable bundle):**

1. **F-001** — Commit plan `.dev/plans/pacing-before-llm/plan.md` with full §8 handoff and **Status: Complete**, or update closure SHA after commit so `git show <closure>:plan.md` matches the handoff narrative.

**Non-blocking (recommended):**

- **F-003 / F-004** — Refresh T2 decision log deferred section and add CHANGELOG T3 bullet.
- **F-005** — Remove duplicate `.dev/plans/_pending/pacing-before-llm/context-map.md` at HEAD (working tree already deletes it).

**Code quality:** Implementation at `692dfa0c` matches intent and §2 contracts; contract-focused pytest green (21/21 on §8.1 command). Fail verdict is driven by **audit-archive integrity** (`artifact-not-in-HEAD`), not by runtime contract breakage.

---

## 13. Finding status vs prior revision

N/A — initial audit.
