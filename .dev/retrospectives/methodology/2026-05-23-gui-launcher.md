# Retrospective — methodology — gui-launcher

**Date:** 2026-05-23  
**Plan:** `.dev/archive/gui-launcher/plan.md` **v1.0 → v1.1** (T5 amendment; orchestrator-planning **v0.6**)  
**Context map:** pre-plan-exploration **v0.2** @ scout `dcc28d71ebb140b57bdda74951f21fda75922918` (never rescouted)  
**Audits:** `.dev/audits/2026-05-17-gui-launcher.md` — **first pass only**, verdict **`fail`** @ `56c3748e99ea84bb6fa398bbaf474e0508918a99` (no re-audit in repo)  
**Artifacts read:** archived `plan.md` §0–§8, `context-map.md`, packets **T1–T5**, `gui-T1.md`, `gui-T3.md`, audit report, `git log` for `58b0bb76` → `56c3748e` → `1d8eaaee` → `bb7746aa` (archive move).

**One line — what the task was:** Extract `PipelineController` + `ReactorHolder` and worker callbacks from monolithic `pipeline.main()`, thin the CLI, add a PyQt6 `heckler-gui` launcher with live feeds and runtime mode/persona controls, and document the new entry point.

---

## 1. Task identifier

- **Name:** gui-launcher  
- **Dates:** exploration **2026-05-16**; execution **2026-05-17**; audit **2026-05-17**; plan tree archived **2026-05-22** (`bb7746aa`)  
- **Plan versions:** **1.0** (T1–T4 DAG), **1.1** (T5 amendment + §2 status-string contract + T2 packet re-emission)  
- **Orchestrator / executor:** Full plan + packets; architectural logs **T1**, **T3**; standard **T2**, **T5**; trivial **T4**

---

## 2. Plan vs reality

### DAG vs execution

**Mostly matched; two sequencing deltas:**

| Planned | Actual (git) | Notes |
|---------|--------------|-------|
| T1 → T5 → T2 | `58b0bb76` → `e5cadf8b` → `bd41e55f` | Amendment before CLI adapter — **correct** and necessary after T2 HALT. |
| T1 → T3 ∥ T2 (after T5) | T3 landed in `56c3748e` **after** T2 (`bd41e55f`) and T4 (`c2fd91e4`) | Parallel group **not used**; no file overlap would have made `{T2,T3}` safe, so this is **process inefficiency**, not unsafe parallelization. |
| T2,T3 → T4 | T4 (`c2fd91e4`) **before** T3 | README updated while GUI still in the same-session batch; **harmless** given T4 only touches `README.md`. |

**Mermaid DAG held for dependencies that mattered:** T2 never ran on pre-T5 controller; T3 only needed T1.

### Contracts at the implementation surface (§2)

**Runtime contracts held** where the audit exercised them:

- §8.3 maps every §2 row to `heckler/controller.py`, `pipeline.py`, `gui/`, `pyproject.toml`, and named pytest cases.
- Audit Phase 4: **66 passed** (`test_controller`, `test_pipeline`, `test_gui`); integration seams (SignalBridge, mode-aware `load_models`, `ReactorHolder`, legacy CLI banners) **verified** in code + tests.
- No audit signal of **hollow contracts** (e.g. declared types with `getattr` defaults and no behavior). `load_models(mode=)` and status-string tables are **falsified** by controller tests, not only grep.

**Residual gaps (explicitly waived / minor, not §2 violations):**

- `ModelLoadThread.run` exception → `QMessageBox` path: **no automated test** (audit CR-1 / F-5).
- WASAPI / torch+PyQt6 install matrix: deferred in `gui-T1` / `gui-T3` with audit acknowledgment.
- Task wording “live transcript **and** reaction **feeds**” vs single interleaved `QPlainTextEdit` (audit F-4 / CR-2) — UX wording, not a broken callback contract.

### §2 / decision-log narrative survival

| Artifact | Drift | Repaired? |
|----------|-------|-----------|
| Plan §0 “map is fresh / zero in-scope source changes” | **False** vs `git diff dcc28d71..HEAD` on `pipeline.py`, `pyproject.toml` (audit **F-1**, **F-PROV-1**) | **No** — still in archived `plan.md` |
| Plan §8 “Complete” + **PROVISIONAL** T3 uncommitted | Accurate mid-session; **obsolete** after `56c3748e` | **No** §8 refresh before audit (**F-3**) |
| Plan §8.1 SHA `c2fd91e…` | Superseded by `56c3748e…` at audit HEAD | **Not updated** in plan |
| `gui-T1.md` — `main()` imports `ReactorHolder` inside `main()` | Shipped `main()` imports only `ControllerCallbacks`, `PipelineController` (**F-2**) | **No** |
| Context map line-level `pipeline.py` cites | Stale-qualified after T1–T3 landings | **No** rescout |

Downstream plans (`locale-lang-propagation`, `pacing-before-llm`) already treat **gui-launcher map/logs as historical baselines** — sensible damage containment, not a substitute for rescouting or §0 amendment.

### Log tiers

| Subtask | Tier | Calibration |
|---------|------|-------------|
| T1 | architectural | **Appropriate** — new controller pattern, hot-swap, mode teardown. |
| T3 | architectural | **Appropriate** — Qt package, signal bridge, loader thread. |
| T2 | standard | **Appropriate** — thin adapter. |
| T5 | standard | **Appropriate** — contract-anchor fix after HALT; not a new architecture. |
| T4 | trivial | **Appropriate**. |

Nothing clearly over- or under-tiered in hindsight. T5 could be argued “architectural” because it **amended §2**, but scope was alignment-only — **standard** is defensible.

### Closure vs committed reality

**Leak at multiple layers:**

1. **Mid-flight honesty, then stall:** §8.1 **PROVISIONAL** correctly flagged T3 + plan artifacts uncommitted; `56c3748e` committed them (~17h before audit) but **§8 was not rewritten** to a non-provisional closure table (**F-3**).
2. **Wrong closure SHA narrative:** §8.1 cited `c2fd91e…` (T1+T5+T2+T4); audit HEAD `56c3748…` includes T3 + full plan tree (**audit** notes SHA mismatch).
3. **Context map never moved off scout SHA** `dcc28d71…` while §File map **direct** paths changed — audit **`fail`** blockers **F-PROV-1**, **F-1**.
4. **No re-audit / no post-audit hygiene subtask** (contrast **transcription-engine** T6 + rev 2 `pass`). Audit committed `1d8eaaee`; plan archived `bb7746aa` **without** map refresh or §0 fix.
5. **Path archaeology:** Audit binds `.dev/plans/gui-launcher/…`; tree now `.dev/archive/gui-launcher/…` — readers must translate paths; audit text was not revised on archive.

**First audit tree state:** Audit metadata claims **clean** working tree @ `56c3748e` — good discipline for runtime verification; planning-artifact staleness is separate from dirty-tree execution.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**One documented, correct HALT chain (T2 → T5):**

T2 could not land CLI parity without:

1. `load_models()` loading Speaker in transcribe mode (violates `test_main_transcribe_mode_does_not_load_speaker_or_reactor`).
2. Controller status strings missing legacy `/ CUDA`, `Kokoro /`, timing, and mode-specific mic-open lines; spurious `Running in {mode} mode.`
3. **`tests/test_pipeline.py` outside T2’s original Files to touch** — executor correctly refused to improvise cross-boundary test edits.

Orchestrator response: **plan v1.1**, insert **T5** `T1 → T5 → T2`, re-emit **T2** packet, add §2 status-string contract. Commits: `e5cadf8b` (T5) then `bd41e55f` (T2).

**Assessment:** **Correct HALT** — real contract drift between T1 controller and legacy `main()`/tests, not executor timidity. The HALT report itself is **not** a separate tracked file; it lives only in plan §7 / packet preambles — **minor archaeology gap** if chat logs are lost.

**False HALTs:** **nothing notable** in artifacts.

**HALT-shaped silent improvisation:**

- **nothing notable** on kill criteria (workers, AudioCapture join, pytest regressions) — T1 landed without HALT transcripts.
- **Opposite leak:** declaring plan **Complete** with §8 **PROVISIONAL** was honest; **failing to de-provision §8 after `56c3748e`** is completion narrative drift without a HALT — caught by audit **F-3**, not by executor.

### Amendment cycles

| Cycle | Trigger | Scope | Closed? |
|-------|---------|-------|---------|
| **T5** | T2 HALT (pre-audit) | `controller.py`, `test_controller.py`, §2 back-annotation | **Yes** — T2 then passed in `bd41e55f` |
| **(none)** | Audit `fail` F-PROV-1, F-1 | Context map + §0 provenance | **No** — no T6-shaped subtask; archived instead |

T5 scope was **right-sized** (no GUI reopen, no controller redesign). **First execution pass** for T5 — no multi-spin amendment.

**Post-audit:** For an **architectural-tier** task (T1+T3), **zero audit-driven amendments** — not because first audit was clean (`fail`), but because **no re-audit loop ran**. Audit signal on provenance was **sharp enough**; **closure process** did not consume it.

---

## 4. Adversarial pass calibration

### Rejected alternatives (§5.1)

- **Monolith single subtask** — rejection validated; HALT on T2 would have been harder to isolate.
- **Controller in `heckler/gui/`** — rejection validated; CLI imports `heckler.controller` cleanly.
- **Optional PyQt6** — user chose **required**; audit ruled out “optional-only” packaging risk; held.
- **Merge T1+T2** — separation allowed T5 to target controller without touching GUI.

**nothing notable** that would have clearly produced a better outcome given what actually failed (CLI string parity, not Qt layout).

### Load-bearing assumptions (§5.2)

Plan §8.4 + audit §10 reconciliation: **all five §5.2 assumptions closed** at audit time (lock-backed `ReactorHolder`, 120s joins, shared Transcriber/Speaker, AudioCapture join, PyQt6 install smoke).

Runtime-only risks (LLM-blocking stop, WASAPI hang) **explicitly accepted** in `gui-T1.md` — consistent with “deferred, not hidden.”

### Highest re-plan risk (§5.3)

**Predicted:** T1 mode-switch teardown / AudioCapture races.

**Outcome:** **Did not** force replan. `test_switch_mode_rebuilds_topology` + controller code satisfied audit S4. **Trouble came from elsewhere:** T2 legacy CLI parity and **narrow Files to touch** — exactly §5.4 coupling #4 (stdout vs callbacks) and the **T2 HALT**, not the predicted teardown catastrophe.

---

## 5. Methodology gaps surfaced

**Orchestrator / §0 intake**

- §0 “staleness check” equated “no changes between map SHA and **plan author’s HEAD**” with “map fresh for execution.” **T1–T3 changed** `pipeline.py` and `pyproject.toml` — the check should require `git diff <map-sha>..<execution-start>` on §File map **direct** rows, or mandate rescout after T1 lands.
- CONDITIONAL flags (controller location, hot-swap, PyQt6) were **resolved in plan text** but map body was never regenerated — downstream tasks inherit **stale line numbers** (persona-system / transcription-engine audits show the same failure mode).

**Orchestrator / §8 closure**

- **PROVISIONAL** handoff is good; missing **“close §8 when provisional list empties”** allowed Complete + stale §8.1 SHA to coexist with green tests.
- No **post-audit amendment** template was invoked (unlike persona-system T7, transcription-engine T6). **Archive ≠ audit remediation.**

**Executor**

- `gui-T1.md` narrative about `ReactorHolder` import site **wrong vs shipped `main()`** — decision logs should be reconciled to code before §8 auditor handoff (audit **F-2**).
- T2 HALT was **effective** but **not filed** as `.dev/halts/` or decision-log entry — only plan §7. Harder to retrospective without chat.

**Auditor / follow-through**

- Audit correctly **`fail`** on provenance; **no revision 2** in repo — methodology stopped at “findings listed” while code shipped and plan moved to **archive**.

**Contracts schema**

- **Status-string contract** as a dedicated §2 subsection (T5) worked well — gave T2 kill criteria literal targets.
- **nothing notable** vestigial in schema; optional gap: require **HALT artifact path** in plan §7 when amendment fires.

**Skill edits:** Do not edit skills here. Cross-retro pattern: **`git show HEAD:` matrix for every §8.2 row** before “Complete”; **rescout or §0 amendment** when `dcc28d71..HEAD` touches §File map direct paths.

---

## 6. Single sentence verdict

**Partially** — the **T2 HALT → T5 amendment → T2** loop and **§2 runtime contracts** (66 tests, scout predictions largely verified) show the orchestrator/executor methodology **working on integration**; it **leaked on provenance and closure** (false §0 freshness, stale context map, unrevised §8 after commit, audit **`fail`** with **no re-audit or hygiene subtask** before archive), so merge-readiness **archaeology did not hold** even though the shipped controller/GUI slice was technically sound.
