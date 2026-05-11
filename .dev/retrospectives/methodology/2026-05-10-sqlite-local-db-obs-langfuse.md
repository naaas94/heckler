# Methodology retrospective — sqlite-local-db-obs-langfuse

Personal notes. Filed 2026-05-10.

## 1. Task identifier

- **Task:** sqlite-local-db-obs-langfuse (SQLite steady-state store, reactor-local LiteLLM observability scaffold, optional legacy JSONL import).
- **Date (execution / closure):** 2026-05-09; this retrospective filed 2026-05-10.
- **Plans / skills:** `.dev/plans/sqlite-local-db-obs-langfuse/plan.md` **v1.1.0**; orchestrator-planning **v0.5** (per plan header); pre-plan map **v0.2**; executor-subtask-execution implied by packets; adversarial audit `.dev/audits/2026-05-09-sqlite-local-db-obs-langfuse.md` **v2.0**.
- **One line:** Replace JSONL persistence with SQLite + tracing correlation + docs/tests, optional import script.

## 2. Plan vs reality

- **DAG vs execution:** Planned **{T1, T2}** parallel, then **T3** / **T4** with a documented soft ordering preference (**T4 → T3** if wiring fights). Landed narrative in `CHANGELOG.MD` follows **T1 → T2 → T3 → T4 → T5 → T6** (sequential story). No evidence parallel **T3**/**T4** caused unsafe merges; audit §12 marks the **T3 ∥ T4 import drift** suspicion **ruled-out** with green pytest. nothing notable on unsafe parallelization beyond “soft dependency worked or was respected.”
- **Contracts:** Core §2 bindings (config field/env, store API, single `serialize_heckle_event` projection, logger signatures, `LLM_ERROR` envelope, CLI freeze, T6 script-only) **held** at audited `HEAD`; audit Phase 2 table is all **pass**. **Drift** was **meta-contract**: plan §8 “tree SHA at plan closure” (**`b9b24afb…`**) did not match the commit that actually contains `heckler/event_store.py` (audit **D1**); **T13** decision log prose still described interim JSONL after T2 (audit **F2**) — documentation lag, not runtime contract break.
- **Log tiers:** **T1–T4** marked **architectural**, **T5–T6** **standard** — appropriate for where risk lived (store/threading, config migration, logger seam, reactor). **T6** as standard matches optional tooling; no clear mis-tiering.

## 3. HALTs and re-plans

- **Documented executor HALTs:** nothing notable — no HALT paper trail in changelog or decision logs visible from this pass (kill criteria remained hypothetical).
- **Re-plan cycles:** nothing notable as a formal orchestrator **§7** amendment; plan stayed **v1.1.0** with a **Landed** narrative block rather than a new subtask DAG.
- **Audit / quality gate friction (process, not executor HALT):** audit **v1.0** **F1** (review vs wrong / uncommitted tree) forced a **v2.0** re-run — correct adversarial catch, not a packet HALT.
- **Silent improvise?** Low suspicion: code, tests, and audit traceability align with §2; the gaps were **closure provenance** and **stale decision-log prose**, not undisciplined scope creep.

## 4. Adversarial pass calibration

- **Rejected decompositions (§5.1):** The rejection of a single mega-subtask **mattered in hindsight** — bounded files per Tn match the clean integration story in audit §7 / §12.
- **Load-bearing assumptions (§5.2):** Held per audit §12 (stdlib SQLite + WAL, LiteLLM `metadata` surface, reaction-thread correlation, single serialization path).
- **§5.3 highest re-plan risk (T3):** **Partially predictive** — the risk class (logger + serialization + DB + tests) was real, but **trouble in practice** showed up more as **audit/doc/provenance** issues (**D1**, **F2**, v1 **F1**) than as a blown T3 integration. Row-shape / correlation concerns were **test-backed down** (audit adversarial table A1–A7).

## 5. Methodology gaps surfaced

- **Orchestrator / closure:** §8 **tree SHA** should be mechanically verified against “first commit containing the named new artifacts” before marking **Complete**; stale SHA undermines auditor handoff (**D1**).
- **Executor / decision logs:** Architectural logs (**T13**) need a **post-land sync** when later subtasks change the story (interim JSONL → gone after **T3**) — else audit flags **decision-log-stale** (**F2**).
- **Pre-plan / context map:** §5.4 asked for grep disproof of duplicate LiteLLM roots; map’s grep inventory did not mirror that vocabulary (**P1** / **scout-incomplete**) — minor but repeatable.
- **Contracts schema:** nothing notable on missing fields; **§8 SHA** is the standout handoff defect.

## 6. Single sentence verdict

**Partially** — decomposition, contracts, tests, and adversarial audit **did their job** on the engineering outcome, but **closure hygiene** (wrong §8 SHA, stale T13 prose, first audit on wrong tree) shows the methodology **leaked at the documentation / provenance boundary**, not at the executor packet boundary.
