# Learning retrospective — pacing-before-llm

**Date:** 2026-05-23  
**Sources:** `.dev/plans/pacing-before-llm/plan.md` (v1.0), `context-map.md`, packets `T1.md`–`T4.md`, `.dev/decision-logs/pacing-before-llm-T1.md`, `pacing-before-llm-T2.md`, `.dev/audits/2026-05-22-pacing-before-llm.md`, `.dev/retrospectives/methodology/2026-05-23-pacing-before-llm.md`, `thoughts_so_far.md`, `CHANGELOG.MD` pacing section, `heckler/pacing_gate.py`, `heckler/pipeline.py`, `tests/test_pacing_gate.py`, `tests/test_pipeline.py`, `tests/test_controller.py`, `.dev/eval-strategy.md` §4.  
**Code closure SHA (plan §8.1):** `692dfa0c` · **§8 + audit archive:** `bb7746aa`

---

## 1. Task context

**What shipped:** A **pre-LLM cooldown probe** on `PacingGate` (`cooldown_status()`), wired at the top of `_run_reaction_worker` so utterances during the minimum output interval skip `reactor.react()` entirely. The **post-LLM path is unchanged**: after a successful reaction, `evaluate(score)` still gates TTS (including `score_override_threshold`), and `record_output()` still runs immediately before `speaker.speak()`. Persistence and analytics gained a **second pacing-reject cohort**: pre-LLM rows have no `reactor_result`, `passed_score_gate=None`, `llm_latency_ms=None`, and no `event_reactor_results` child; post-LLM pacing rejects still carry the full reactor payload and fire `on_reaction` with `was_spoken=False`. Tests, `eval-strategy.md` §4, and README prose document the split.

**Why this earns a learning retrospective:** The change is small in lines (~20 in `pipeline.py`, ~15 in `pacing_gate.py`) but **architectural in meaning** — it moves a product gate across an expensive boundary (LLM), forces explicit tradeoffs on score override, splits analytics semantics under one `discard_reason`, and touches callback contracts established by gui-launcher. The motive came from **operational evidence** (`thoughts_so_far.md`, session logs): pacing blocked TTS on echo bleed while the reactor still ran, so cost and latency persisted even when audio spam did not.

**Execution sketch:** Scout map @ `58f10f13` (CONDITIONAL) → plan §0 resolved five ambiguity flags → T1 API → T2 pipeline + primary falsifier test → T4 docs (before T3) → T3 controller tests → audit `fail` on uncommitted §8 → `bb7746aa` committed handoff + audit file.

---

## 2. What I now understand that I didn't before

### A gate's position in the pipeline is part of its semantics

Before this task I could describe pacing as “minimum interval between spoken outputs” without noticing that **the implementation had already chosen where that interval applies**: after the LLM, before TTS. That was not a bug in `PacingGate`; it was a **placement decision** inherited from T9. Logs made the consequence visible: `discard_reason=pacing_gate` meant “we paid for a reaction and chose not to speak,” not “we never considered reacting.”

Reordering is therefore not “call the same function earlier.” It is: **which resources does this gate protect?** Pre-LLM pacing protects **API spend and latency**; post-LLM `evaluate(score)` protects **audio spam and enforces override with a score**. Those are related but not interchangeable. Any future gate (density, echo, toxicity) needs the same question answered first: *what work should never start if this fails?*

### Score override is structurally a post-LLM feature

`score_override_threshold` lives in `PacingGate.evaluate(score)` because the only score in the system today is `ReactorResult.score` after `react()`. There is no honest way to “keep override” on a path that never calls the LLM without inventing a **new signal** (heuristic density, cached last score, second cheap model, etc.). Flag 1's resolution — **drop override on pre-LLM skip** — is not laziness; it is acknowledging that override is **defined on generated commentary quality**, not on transcript alone.

The falsifier test `test_cooldown_status_ignores_score_override_while_evaluate_bypasses` encodes that split mechanically: during cooldown, `cooldown_status()` stays `(True, remaining)` even when `evaluate(1.0)` would return `(True, …)`. That test is worth keeping as a **contract anchor** if anyone later tries to merge the two methods.

### One enum value, two analytics cohorts

`DiscardReason.PACING_GATE` now labels rows that must **never** be joined the same way in eval exports:

| Cohort | LLM ran? | Child `event_reactor_results` | Meaning for “near miss” analysis |
|--------|----------|-------------------------------|----------------------------------|
| Post-LLM pacing reject | Yes | Present | High self-score line generated but not spoken |
| Pre-LLM pacing reject | No | Absent | Cooldown volume / cost savings; not a commentary near-miss |

`.dev/eval-strategy.md` §4 finally says this aloud. The lesson generalizes: **when you add a cheaper early exit, stratify on absence of downstream artifacts** (`llm_latency_ms`, child rows, `correlation_json`), not only on `discard_reason`.

### `passed_pacing_gate` tri-state is load-bearing

`None` = pacing not reached (LLM error, score gate). `False` = pacing evaluated and failed (pre- or post-LLM). `True` = passed. Pre-LLM reject uses **`False`**, not `None`, because pacing *was* evaluated — just without a score. Conflating “skipped” with “failed” would break dashboards. The one-line comment on `HeckleEvent` in `models.py` is cheap insurance against a future branch setting `None` “because there was no score.”

### Callback contracts follow object availability, not discard reason

gui-launcher landed `on_reaction(result, was_spoken)` when a **`ReactorResult` exists**. Pre-LLM pacing has no result object, so the callback **must not fire** — same rule as `LLM_ERROR` / `SCORE_GATE`, but for a different reason (skipped work, not failed work). Post-LLM pacing reject still fires with `was_spoken=False` because the GUI may want to show what the model said even when TTS was blocked.

I had to stop thinking “pacing reject” as one GUI event type. It is two.

### `context_buffer.push` on pre-LLM fail is intentional, not sloppiness

Plan resolution A4: still push the user transcript when the LLM was skipped. That means **echo segments during cooldown still enter the rolling window** without a heckle line — context advances, cost does not. Pairing pre-LLM pacing with echo skip (`thoughts_so_far.md` L12) would be the next cost win; the scout correctly separated them (Flag 5). Pacing-only fixes **spam and LLM bills during cooldown**; it does not fix **echo LLM bills when not in cooldown**.

### Threading: shared cooldown math needs a private helper, not nested public calls

T1 rejected `evaluate()` calling `cooldown_status()` because both take `threading.Lock` on a non-reentrant lock → deadlock. The pattern `_cooldown_state_locked()` called under one lock acquisition is the small-scale version of a rule I want reflexive: **extract shared state logic to a private “caller holds lock” helper** when two public methods need the same snapshot.

### Pre-plan “CONDITIONAL” plus plan §0 flag table is the right intake for product ambiguity

The scout listed A1–C2 as open questions without choosing answers — correct role. The orchestrator's §0 table **resolved every flag before packets** (override dropped pre-LLM, event shape, no `on_reaction`, T3 tests planned, echo deferred, push kept, correlation NULL accepted, gui out of scope). That prevented executors from improvising product policy under time pressure. For Heckler, **pacing + override + persistence + GUI** is exactly the kind of cross-cutting ambiguity that should never be left to a single subtask's judgment call.

### `record_output()` before `speak()` is about intent, not playback length

T9 docstring: cooldown reflects **intent to avoid stacked outputs**, not audio duration. Pre-LLM skip does not call `record_output()` because no output was attempted. Post-LLM pass still records at speak time. Moving pacing earlier did not change that invariant — and the audit treated any reorder of `record_output` / `speak` as a kill criterion for good reason.

### Operational → code path: logs drove the right wedge

The motivating observation in `thoughts_so_far.md` — pacing blocks TTS on echoes but reactor still runs — is **generation-adjacent learning**: you only get it from running the system and reading events, not from reading `pacing_gate.py` in isolation. The orchestration stack implemented the fix; this retrospective is where the **domain model** (what “pacing” meant in production) becomes explicit.

---

## 3. Decisions I made and would make again

- **Resolve Flag 1 by dropping score override on the pre-LLM path** — honest given no score; documented in T1/T2 logs and README; falsifier test prevents silent re-merge of semantics.
- **`cooldown_status()` as a dedicated API** instead of `evaluate(score=None)` — keeps analytics tri-state and tests readable; rejected alternatives in plan §5.1 were correctly rejected.
- **Keep post-LLM `evaluate(score)` + full event shape + `on_reaction` on post-LLM pacing fail** — preserves operator visibility for “what the model would have said” and eval near-miss cohort.
- **Ship pacing-only; defer echo / `last_spoken` skip** — avoids speaker-state scope creep in one plan.
- **T2 landing `test_reaction_worker_pre_llm_pacing_skips_react`** — the highest-value falsifier (react not called) was green before T3; correct prioritization even if it blurred DAG labels.
- **`_reaction_worker_pacing_mock` setting `cooldown_status.return_value`** — prevents MagicMock from silently allowing both probe and react; plan §5.4 “suspected” coupling was real and fixable.
- **Let T4 document cohort split before T3 finished controller tests** — parallel group `{T3, T4}` after T2; docs could describe behavior once pipeline landed.

**Generalizable principle:** When moving a gate earlier across an expensive call, **ship the API split, the event-shape split, and the eval doc split in the same arc** — otherwise analytics and GUI lie by aggregation.

---

## 4. Decisions I made that I would change

- **Marked plan Complete / wrote §8 while `git show 692dfa0c:plan.md` still had a §8 stub** — repeats persona-system / capture-mic-gate archaeology failure. **Better rule:** closure SHA for the plan artifact is the commit where `git show <sha>:.dev/plans/.../plan.md` contains §8.1+, or §8.1 must cite a separate `plan_handoff_sha`. Narrative closure ≠ git closure.
- **Left T2 decision log “Items deferred → T3” and CHANGELOG “controller coverage deferred to T3” after T3 landed** — time-indexed docs became false history (audit F-003/F-004). **Better rule:** T3 packet kill criteria should include “strike deferred bullets in T2 log + add T3 CHANGELOG bullet” when parallel order is T4-before-T3.
- **No re-audit after `bb7746aa`** — audit file still says **`fail`** for F-001 even though HEAD fixed it; future me may think pacing never passed merge gate. **Better rule:** one-line audit revision or status table when remediation commit lands.
- **`bb7746aa` commit message bundles capture-mic-gate and pacing-before-llm** — hurts `git log` attribution when bisecting pacing-only behavior. Prefer separate commits or a clear body with scoped paths when two plans land same session.
- **Did not add a “Landed” section to T2 decision log when the primary T3 falsifier appeared in T2** — scope bleed was benign but made T3 look more important in hindsight than it was for pipeline proof.

**Underlying error (again):** optimizing for **implementation closure** and **pytest green** faster than for **time-indexed artifact truth** across commits.

---

## 5. Patterns in my own thinking

- **Initial urge to bundle echo skip with pacing** — `thoughts_so_far.md` lists both mitigations in one breath (L8–12). The scout and plan correctly resisted. I still need a habit: **separate “same symptom” from “same mechanism.”** Echo is acoustic/path; pacing is temporal/rate.
- **Underestimated closure hygiene, overestimated pipeline risk** — plan §5.3 named T2 reorder as highest re-plan risk; actual friction was §8-in-HEAD and stale deferrals. I may still **anchor on code difficulty** when scheduling audit time; for Heckler-sized diffs, **artifact graph** is often the real tail risk.
- **Review-driven execution vs log-driven motive** — agents implemented; I validated. The **why** (LLM cost on echo during cooldown) lived in personal notes and logs, not in the plan's task statement alone. Without this retrospective, the compounding knowledge stays in `thoughts_so_far.md` bullets instead of in **invariants I can cite when designing the next gate**.
- **Comfort with “audit fail on docs”** — improving versus treating audit as enemy, but I should not normalize leaving the audit file in `fail` state after fix.
- **Possible motivated reasoning to avoid:** treating pre-LLM skip as “done” for echo cost because logs showed pacing_gate on echo lines — **echo LLM spend outside cooldown is still open** (A3 deferred).

---

## 6. Open questions

- **Echo skip without `last_spoken` in repo:** What is the minimal state — hash of last spoken comment on `Speaker`, pipeline field, or transcript similarity heuristic? How does it interact with pre-LLM pacing (skip react when echo *or* cooldown)?
- **Override without full LLM:** Is there any cheap signal (e.g. density + keyword trigger) worth a second plan, or is “accept no override during cooldown” stable product policy?
- **Pre-LLM skip volume vs lowered cooldown (A5 deferred):** Shorter `min_output_interval_s` increases how often `cooldown_status` fires — composes nonlinearly with LLM savings; worth simulating on exported JSONL cohort counts.
- **Live clock / e2e:** Unit tests monkeypatch `time.time`; is wall-clock drift or worker backlog ever visible in production cooldown edges?
- **SQLite integration test for pre-LLM insert:** Audit accepted event-field tests only; is a single `insert_heckle_event_row` test with `reactor_result=None` worth it when analytics bugs appear?

---

## 7. Single paragraph synthesis

**pacing-before-llm** taught that a gate's **position in the pipeline is part of its product meaning**: moving cooldown before the LLM is not a refactor of `PacingGate`, it is trading **score-based override during cooldown** for **LLM cost savings**, and that trade only stays honest if analytics (`PACING_GATE` cohorts), persistence (no child row), and GUI callbacks (`on_reaction` requires `ReactorResult`) **split with the gate**. The implementation was technically straightforward; the compounding work is remembering that **operational logs revealed the wrong boundary**, that **override is structurally post-LLM until a new signal exists**, and that **the same failure mode as persona-system — narrative “complete” before `git show HEAD` agrees — still happens unless handoff SHA and deferred-doc reconciliation are part of done**, not an audit aftermath.

---

## Cross-links (for future you)

| Artifact | Role |
|----------|------|
| Methodology twin | `.dev/retrospectives/methodology/2026-05-23-pacing-before-llm.md` |
| Audit (initial `fail`, F-001 remediation) | `.dev/audits/2026-05-22-pacing-before-llm.md` |
| Plan + §8 evidence | `.dev/plans/pacing-before-llm/plan.md` |
| Motive notes | `thoughts_so_far.md` L8–16, L24 |
| Prior callback contract | `.dev/decision-logs/gui-T1.md` |
| Learning pattern peer | `.dev/retrospectives/learning/2026-05-16-persona-system.md` (HEAD / deferred-doc class) |

**Code anchors:** `heckler/pacing_gate.py` (`cooldown_status`, `_cooldown_state_locked`, `evaluate`); `heckler/pipeline.py` `_run_reaction_worker` L179–199 (pre-LLM) vs L240+ (post-`react` evaluate); `tests/test_pipeline.py::test_reaction_worker_pre_llm_pacing_skips_react`.
