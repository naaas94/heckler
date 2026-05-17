# Retrospective — methodology — persona-system

**Date:** 2026-05-16  
**Plan:** `.dev/plans/persona-system/plan.md` — **v1.0 → v1.1** (T7 audit remediation narrative in §0 / §7 / §8)  
**Context map skill:** pre-plan-exploration **v0.2** (intake §0; T7 rescout regen)  
**Artifacts read:** plan §0–§8, `context-map.md` (header + scope/file-map slice), packets dir listing, `.dev/audits/2026-05-16-persona-system.md` (**revision 3**), `.dev/decision-logs/persona-system-T1.md`, `persona-system-T3.md`, `.dev/persona-system.md` cited by plan as informational only.

**One line — what the task was:** Introduce swappable persona bundles (`prompts/<persona>/`), `heckler/persona.py`, config/env/CLI wiring, reactor refactor + UNKNOWN fallback, migrate default prompts to `prompts/heckler/`, then **close audit findings** on planning hygiene (FIND-01–03) via **T7**.

---

## 1. Task identifier

- **Name:** persona-system  
- **Date:** 2026-05-16  
- **Plan versions:** **1.0** (T1–T6 landed; audit **fail**), **1.1** (T7 + §0/§8 refresh for FIND-01–03)  
- **Orchestrator / executor pairing:** Full plan + packets T1–T7 + adversarial §5; executor-style landings reflected in plan §8 completion table and audit chain.

---

## 2. Plan vs reality

- **DAG vs execution:** Matches. `{T1, T2, T3, T4}` parallel → **T5** integration → **T6** cross-cutting/docs → **v1.0 audit fail** → **T7** amendment chain `T6 → T7`. No evidence parallelization was unsafe for declared file ownership; the real sequencing pressure was **audit-driven** doc work after implementation, not a surprise merge conflict in the parallel group.
- **Contracts at implementation surface (§2):** **Held** where audited. Revision 3 audit Phase 2 summary: §2 types, logging literals, TOML mapping, CLI, error envelope, and named tests verified against `heckler/` + `tests/`. No hollow-contract signal (e.g. tests green while §2 symbols missing) in the audit narrative after T7 map regen.
- **§2 / decision-log narrative survival:** **Drift then repair.** `persona-system-T3.md` **Items deferred** read as current facts after T5 (**FIND-02**); **T7** superseded with **Landed** prose aligned to `pipeline.py` / `test_pipeline.py`. Plan §0 also corrected staleness methodology under-play (**FIND-01**). Residual **narrative staleness** in plan §5.4 hidden-coupling #1 parenthetical (`Reactor(config)` line cite) called out in audit Phase 1 as **observation** — minor prose lag, disposition table already marks coupling resolved.
- **Log tiers:** **T1 / T3 `architectural`** — appropriate (new module + reactor semantic change). **T2 / T4 / T5 / T6 / T7 `standard`** — appropriate; T7 was docs-only but still audit-load-bearing. Nothing clearly over- or under-tiered in hindsight.
- **Closure vs committed reality:** **Leak.** Plan §6 / §8 **artifact chain** lists `packets/T7.md` as tracked; re-audit **FIND-ARCH-1**: `git show HEAD:.dev/plans/persona-system/packets/T7.md` **fails** — file **untracked** on disk. So §8 “Complete” and closure table **over-claim** merge archaeology vs **`HEAD`**. Map baseline `026d68d` / per-row `diff --quiet` story **holds** for listed code paths; the gap is **planning packet in git**, not runtime tree. First-pass v1.0 audit used a **stale context map** relative to post-land paths — **caught** by audit (correct); T7 remediated FIND-01–03 but **re-audit** still **`fail`** until T7 packet is committed (revision 3 verdict).

---

## 3. HALTs and amendment cycles

- **Executor HALTs:** **nothing notable** — no `HALT` markers or halt narratives in searched `.dev` persona artifacts or decision logs; kill criteria in packets/plan read as satisfied without documented escalation.
- **HALT-shaped silent improv:** **nothing notable** — audit explicitly re-verified kill-criterion-style checks (e.g. §File map paths exist at map SHA; pytest **202** passed).
- **Amendment cycles:** **One audit-driven amendment track (T7)** for FIND-01 (context map), FIND-02 (`persona-system-T3.md`), FIND-03 (T2 packet / plan §4 alignment). Scope stayed **planning hygiene** — no runtime §2 reopen — **right-sized**. **Did not close at first re-audit:** revision 3 introduced **FIND-ARCH-1** (packet not in **`HEAD`**), so amendment **closed the original audit majors** but left a **process/archaeology** major. Not “audit too weak,” but **closure checklist vs git** too weak on the last artifact.

---

## 4. Adversarial pass calibration

- **Rejected alternatives (§5.1):** **nothing notable** that invalidated the decomposition later; parallel leaf + T5 integrator pattern matched how the work landed.
- **Load-bearing assumptions (§5.2):** Audit disposition table + revision 3 recon — **held** (tomllib/`>=3.11`, keyword `HecklerConfig`, UNKNOWN path, prompt `Path(__file__)` resolution, monkeypatch updated, map baseline **closed** post-T7).
- **§5.3 highest re-plan risk (T1 TOML mapping):** **Did not** become the failure axis in audit narrative; friction was **staleness of planning artifacts** (map, T3 log) and **undeclared** bundle test vs T2 packet (**FIND-03**), all **doc/plan** tier. **Trouble came from elsewhere** than the predicted T1 mapping crisis — though §5.4 **did** pre-register decision-log and T7.md supersession risks that **materialized** as FIND-02 / historical T7 assumption noise (later superseded in code + logs).

---

## 5. Methodology gaps surfaced

- **Orchestrator / §8 closure:** Should treat **“packet emitted”** as **`git ls-files` / `git show HEAD:`** true, not “file exists in worktree.” Plan §8 completion table claimed T7 packet complete while revision 3 proves **`HEAD` gap** — **FIND-ARCH-1**.
- **Executor (T7):** Emitting `packets/T7.md` without **`git add`** (or explicit “untracked — user must commit” handoff in the same breath as §8.1) breaks **merge archaeology** invariant the auditor skill enforces.
- **Contracts schema:** **nothing notable** — §2 stayed the normative runtime contract; T7 correctly avoided editing §2 for doc-only remediation.
- **Skill edits:** Per retrospective skill — **do not edit skills here**; note only: consider a cross-skill prompt that **artifact matrix rows must resolve via `HEAD`**, not editor buffers.

---

## 6. Single sentence verdict

**Partially** — the DAG, §2 runtime contracts, and audit→T7 loop **did their job** on FIND-01–03, but **closure vs `HEAD` leaked** (**FIND-ARCH-1**: `packets/T7.md` declared tracked yet not committed), so methodology **held for implementation and contract verification** and **failed merge-readiness archaeology** until that gap is fixed.
