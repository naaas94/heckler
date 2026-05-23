# Retrospective — methodology — pacing-before-llm

**Date:** 2026-05-23  
**Plan:** `.dev/plans/pacing-before-llm/plan.md` v1.0  
**Context map:** pre-plan-exploration v0.2 @ scout `58f10f132078691a70cc0ae70a5304816fce1f25`  
**Orchestrator:** orchestrator-planning v0.6  
**Artifacts read:** `context-map.md`, `plan.md` §0–§8, packets T1–T4, decision logs T1–T2, audit `.dev/audits/2026-05-22-pacing-before-llm.md`, `CHANGELOG.MD` pacing section, `bb7746aa` / subtask commit range `25ff36f9`→`692dfa0c`, implementation spot-check `heckler/pacing_gate.py`, `heckler/pipeline.py`, `tests/test_*`.

**One line — what the task was:** Add `PacingGate.cooldown_status()`, call it before `react()` in `_run_reaction_worker` to skip the LLM during cooldown, keep post-`react()` `evaluate(score)` + TTS (including score override), and split persistence/analytics/docs for pre-LLM vs post-LLM pacing rejects.

---

## 1. Task identifier

- **Name:** pacing-before-llm  
- **Execution date:** 2026-05-22 (audit + §8 fix same day; this retro 2026-05-23)  
- **Plan version:** 1.0 (no §7 amendments)  
- **Closure / code SHA cited in plan §8.1:** `692dfa0c9a398544b611d1d59b7609f8e0609261` (T3 commit)  
- **§8 + audit archive commit:** `bb7746aaf1146371fcd0f7a59ba83111fee0cad4` (bundled with unrelated capture-mic-gate narrative in message)  
- **Subtask commits (landed order):** `25ff36f9` (T1) → `0da7ac52` (T2) → `ca397e9e` (T4) → `692dfa0c` (T3)

---

## 2. Plan vs reality

### DAG vs execution

- **Planned DAG:** `T1 → T2 → {T3, T4}` parallel after T2.  
- **Actual:** `T1 → T2 → T4 → T3`. Parallel group honored (T4 before T3); no unsafe overlap on production files — T4 touched docs + plan bundle; T3 only `tests/test_controller.py` + small `test_pipeline.py` deltas.  
- **Sequencing surprise (process, not technical):** T4 landed **before** T3, so `CHANGELOG.MD` and T2 decision log still say controller `on_reaction` coverage is **deferred to T3** at T4 commit time — accurate at commit time, but **never reconciled** after T3 (`692dfa0c`). Audit F-003/F-004 flagged this; still open at HEAD.

### Subtask scope bleed

- **T2 shipped T3 kill-criterion work:** `test_reaction_worker_pre_llm_pacing_skips_react` and `_reaction_worker_pacing_mock` landed in `0da7ac52`, not in T3. T3 then focused on controller falsifiers and post-LLM assertion tightening.  
- **Effect:** Kill criteria were satisfied earlier than the DAG labels suggest; T3 became **narrower** than the packet implied. Not harmful (tests exist), but **log-tier narrative** (T3 = “adversarial coverage”) understates that the hardest pipeline falsifier was already green after T2.

### Contracts at implementation surface (§2)

| §2 topic | Enforced? | Notes |
|----------|-----------|--------|
| `cooldown_status` | Yes | `tests/test_pacing_gate.py` + pipeline/controller mocks |
| `evaluate` unchanged | Yes | Existing unit tests + `test_cooldown_status_ignores_score_override_while_evaluate_bypasses` |
| Pipeline order | Yes | `test_reaction_worker_pre_llm_pacing_skips_react`, post-LLM test retained |
| Pre-LLM `HeckleEvent` shape | Yes | Field assertions in pipeline test |
| `passed_pacing_gate` tri-state | Yes | `models.py` comment + branch coverage in tests |
| `on_reaction` rules | Yes | `test_on_reaction_not_fired_on_pre_llm_pacing` + post-LLM pacing callback test |
| `record_output` before `speak` | Yes | `test_execute_spoken_reply_records_before_speak` |
| Error envelope | Yes | No new types; branches untouched |
| CLI | N/A | — |
| SQLite child row absent pre-LLM | Partial | `event_store` insert guard + event shape tests; **no** dedicated insert_rollback test (audit: acceptable) |

**Hollow-contract check:** No signal that tests pass via `getattr` defaults or dropped unknown keys — mocks explicitly set `cooldown_status.return_value`; assertions target `reactor_result is None`, `passed_score_gate is None`, `llm_latency_ms is None`.

### §2 / decision-log narrative survival

- **Plan §0 flag resolutions → code:** Held. All five context-map flags plus A4/A5/B4/C2 resolved in plan §0 before packets; implementation matches (override dropped pre-LLM, event shape, no pre-LLM `on_reaction`, echo out of scope).  
- **Stale narrative after downstream work (unrepaired):**  
  - `pacing-before-llm-T2.md` **Items deferred** still points controller falsifiers to **T3** after T3 landed.  
  - `CHANGELOG.MD` T2 bullet still defers `test_controller.py` to T3; **no T3 bullet** for controller tests / strengthened pipeline assertions.  
  - Plan §8.4 **open hygiene** documents CHANGELOG gap; audit recommended fix — **not done** by `bb7746aa` (that commit only added audit + full §8).  
- **Scout map vs implementation:** Expected divergence (scout `58f10f13` vs code `692dfa0c`). Plan and audit correctly stale-qualify line citations; directional couplings still valid.

### Log tiers

- **T1 / T2 `architectural`:** Appropriate — new public API + pipeline reorder + event semantics.  
- **T3 / T4 `standard`:** Appropriate for test/doc slices.  
- **Minor calibration note:** T2’s architectural commit already contained the primary adversarial pipeline test; T3’s `standard` tier understates how much “architectural proof” was already on main after T2.

### Closure vs committed reality

- **Code closure SHA `692dfa0c`:** Correct first commit containing full pacing implementation + plan-listed tests. Re-run 2026-05-23: **21/21** on plan §8.1 pytest command.  
- **Plan §8 at cited closure SHA:** **Leak (F-001).** `git show 692dfa0c:plan.md` had §8 stub only; **Status: Complete** and §8.1–§8.6 existed only in working tree when audit ran.  
- **Repair:** `bb7746aa` committed full §8 + audit report. `git show HEAD:plan.md` now has Complete + handoff — **F-001 closed** for archaeology.  
- **Closure SHA vs §8 commit mismatch:** Plan §8.1 still names tree SHA `692dfa0c` while §8 body landed in **`bb7746aa`**. Auditors using only `692dfa0c` get code + stub plan; auditors using `bb7746aa` get full chain. Not wrong for *code*, but **handoff SHA is split across two commits** without plan amendment.  
- **First audit tree state:** Audit HEAD = `692dfa0c` with **dirty** plan working tree — auditor read §8 from disk (correct discipline per audit §3) but verdict **`fail`** on `artifact-not-in-HEAD` until `bb7746aa`.  
- **Context map pinned SHA:** Still scout `58f10f1` in map header; plan §8.2 marks stale — intentional, not repaired (no T7 rescout).  
- **`_pending/` duplicate map:** Tracked at `692dfa0c`; **removed** from git by later work (not in `git ls-files` at HEAD). F-005 hygiene closed.  
- **No §7 amendment subtasks:** Audit failure did not spawn T7-shaped remediation — single follow-up commit instead.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Zero** documented HALTs in decision logs, packets, or commit messages. Kill criteria in T1–T4 appear satisfied without escalation.

### HALT-shaped silent improv

- **T2 → T3 test overlap:** T2 implemented the Flag 4 / T3 kill test without amending the plan or halting — convenient, but **blurs subtask boundaries** and leaves T3 packet “suggested tests” partially already done. Not a contract violation; a **process softening** of strict packet ownership.  
- **§8 “Complete” before §8 in git:** Handoff narrative written and audit run while plan stub still at closure SHA — **kill criterion for merge archaeology treated as satisfied in working tree** until audit forced commit. Similar pattern to persona-system FIND-ARCH-1 family, but **caught before merge narrative was trusted** (audit `fail`).

### Amendment cycles

- **§7:** None at v1.0.  
- **Audit-driven remediation:** Not formalized as T7 — **`bb7746aa`** added `.dev/audits/2026-05-22-pacing-before-llm.md` + committed `plan.md` §8. Scope **right-sized** (no code churn).  
- **Re-audit:** **No revision 2** audit doc — pacing audit remains **`fail`** in the file text (blocking F-001) even though F-001 is fixed at HEAD. Archive/process gap: audit markdown not updated to `pass` after remediation.  
- **Non-blocking audit recs (F-003, F-004):** **Latent** — decision log + CHANGELOG still stale.

---

## 4. Adversarial pass calibration

### Rejected decompositions (§5.1)

- **Hybrid pre-LLM + heuristic override**, **echo bundled**, **`evaluate(score=None)`** — none resurfaced during execution; final shape (`cooldown_status` + unchanged `evaluate`) matches rejected-alternative reasoning.

### Load-bearing assumptions (§5.2)

| Assumption | Outcome |
|------------|---------|
| Pre-LLM skip without override acceptable | **Held** — product tradeoff documented T1/T2/T4; falsifier test exists |
| Single reaction worker serializes | **Held** — documented T2 log; no concurrent test (architectural) |
| `event_reactor_results` only with `reactor_result` | **Held** — guard unchanged |
| gui-T1 `on_reaction` authoritative | **Held** — split pre/post tests |
| Operators accept LLM savings | **treat-as-prediction** — code only; audit agrees |

### Highest re-plan risk (§5.3: T2 pipeline reorder)

- **Technical surprise:** **Low.** Pre-LLM branch (L179–199) is isolated; post-`react()` path preserved; no reported ordering bugs.  
- **Actual friction:** **Closure / doc hygiene**, not pipeline logic — aligns with “trouble came from elsewhere” vs §5.3 headline, though §5.4 already listed decision-log staleness and MagicMock coupling (latter **closed** in T2/T3).

### Hidden couplings (§5.4)

- All **confirmed** couplings in plan §8.4 marked **closed** with tests or code inspection.  
- **Suspected** MagicMock / `cooldown_status` — **disproven** via `_reaction_worker_pacing_mock`.  
- **Surface 7 (`push` on pre-LLM fail):** Intentional per A4 — not a defect.

---

## 5. Methodology gaps surfaced

### Orchestrator / planning

- **§8 completion vs `git show HEAD:plan.md`:** Orchestrator (or handoff author) populated §8 and **Status: Complete** while closure SHA `692dfa0c` still had a stub — same class of leak as persona-system / capture-mic-gate audits. **Audit skill worked**; **§8.1 should either require the §8 commit SHA or block “Complete” until `git show <closure>:plan.md` contains §8.1+.**  
- **T4 before T3:** Allowed by DAG but **CHANGELOG written at T4** baked in “deferred to T3” without a **mandatory post-T3 doc sweep** in T3 packet kill criteria.  
- **CONDITIONAL map intake:** Strong — all flags resolved in §0 before packets; good template for ambiguous pacing/override work.

### Executor

- **T2 landing T3 tests:** Should trigger either (a) HALT/amendment to acknowledge early kill satisfaction, or (b) explicit “T3 scope reduced” note in T2 decision log **Landed** section — not only **Items deferred** pointing forward.  
- **No HALT when writing §8 off-HEAD:** Executor-subtask-execution should treat “commit plan §8 at handoff SHA” as part of T4/T3 closure, not post-audit manual fix.

### Auditor-review

- **Caught F-001** with dirty-tree discipline (read working tree §8, compare to `692dfa0c`).  
- **Gap:** No re-audit pass recorded after `bb7746aa`; report still says **`fail`** while repo HEAD satisfies F-001. Future readers may think pacing failed merge gate permanently.

### Contracts schema

- **nothing notable** — §2 row-per-surface with owning subtask + test path worked well for Phase 4 adversarial table.

### Cross-plan noise (same session)

- `bb7746aa` message bundles **capture-mic-gate-during-play** and **pacing-before-llm** — hurts `git log` archaeology and retro attribution. Unrelated plans interleaved in `25ff36f9^..HEAD` range (audit CR-6 noted capture-mic commits).

### Skill edits

Per skill: **do not edit skills here.** Pattern worth manual promotion: **artifact matrix rows must resolve with `git show <closure>:path>`**, and **post-parallel doc subtask must reconcile CHANGELOG/deferred lines when parallel order inverts**.

---

## 6. Single sentence verdict

**Partially** — the DAG, §0 flag resolution, §2 runtime contracts, and adversarial test plan **held up** and the auditor **correctly failed** incomplete §8-in-HEAD, but **closure narrative leaked across commits** (`692dfa0c` code vs `bb7746aa` plan), **T2/T3 scope and doc deferrals were not reconciled**, and **no re-audit** closed the audit file’s `fail` verdict — so methodology **worked for implementation and contract verification** and **leaked on merge archaeology and post-land hygiene**.
