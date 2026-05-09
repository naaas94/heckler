# Retrospective — Methodology (litellm-provider-switch)

Personal notes. Filed 2026-05-09.

**Retro document version:** **0.2** — revised after **auditor-review** re-pass (**audit document v1.2**, verdict **`pass`**, repo HEAD `94388a98ffd49b68ccbce21f238cabaf429ee166`). **v0.1** body reflected only the **audit v1.1** (`fail`, **F1** blocking) / **T5** issuance window.

## 1. Task identifier

- **Task:** litellm-provider-switch (LiteLLM migration, default `openai/gpt-4o-mini`, multi-provider config).
- **Date:** 2026-05-09.
- **Artifacts:** Plan `.dev/plans/litellm-provider-switch/plan.md` **v1.1 → v1.2.1** (amendment T5); context map from **pre-plan-exploration v0.2**; orchestrator skill referenced **v0.5**; packets T1–T5; audits `.dev/audits/2026-05-09-litellm-provider-switch.md` **v1.1** (`fail`) then **v1.2** (`pass`); decision logs T7, T9, T10, T11; `CHANGELOG.MD` section **litellm-provider-switch**.

## 2. Plan vs reality

- **DAG:** Original graph **T1 → T2 → (T3 ∥ T4)** matched the intended sequencing; **T3** and **T4** remained merge-coordination parallel as planned. **Amendment T5** was not on the original DAG; it followed **audit fail** and plan §7, which is an expected post-audit branch, not ad-hoc replanning of T1–T4 structure.
- **Contracts:** Core §2 bindings for `HecklerConfig`, `load_config`, `Reactor.react`, LiteLLM call shape, error envelope, and tests held in code and tests (audit cold-read and Phase 4 scenarios largely **pass**). **Drift** between `_litellm_auth_params` (**`azure/`**) and shortest §2 / **T11** wording was real (**F3**); remediated by plan v1.2 / **T5** and reflected in T11 *Landed* and plan §2 *Landed* line.
- **Log tiers:** **T1** and **T2** correctly **architectural**; **T3** and **T4** **standard** was directionally right, but **T4’s** narrative work carried a **hard kill criterion** (no false “current” behavior in T7/T9) that was **under-enforced until audit** — tier was not wrong; **acceptance criteria vs executor discipline** was the weak joint.

## 3. HALTs and re-plans

- **Executor HALTs (explicit):** nothing notable in the artifact chain — no recorded HALT stubs or halt-driven packet clarifications in the retained docs.
- **Audit / re-plan:** **v1.1:** verdict **`fail`**, blocking **F1** on **T4** kill vs **T7**/**T9** body text; response was **plan amendment T5** (packet + §7), not a full orchestrator replan of the migration. **v1.2 (re-audit):** **`pass`** — **F1**–**F3** marked **resolved** in the findings table; no new major/critical items; pytest still green at recorded HEAD.
- **Silent improvise vs halt:** **T4** effectively shipped **Landed** errata without satisfying the **letter** of the kill criterion (unfenced “Chosen approach” still read as current → **F1**). That is **executor/review leakage past a condition that should have halted or blocked merge**, caught later by **auditor-review**, not self-corrected in-task.
- **Process log (plan §9):** **T5** packet and remediation edits landed **same session** — a downstream executor-only handoff would see **no diffs** vs kill criteria. That is a **workflow/process** miss (packet vs edit order), not a DAG failure.

## 4. Adversarial pass calibration

- **Rejected decompositions (§5.1):** Still sound in hindsight; no evidence the mega-task or subclass split would have helped; **nothing notable** as “we should have picked the rejected path.”
- **Load-bearing assumptions:** **§5.2-1** (OpenAI-style messages) and **§5.2-4** (default model id) were not the audit’s blocking story; **§5.2-3** (mock stability) did not surface as a fire in this pass. **§5.2-2** (optional keys vs external CI) remained a **latent** risk — audit did not falsify it; **nothing notable** beyond awareness.
- **§5.3 highest re-plan risk (T2):** **Partially predictive** — audit focused **T2/T3** seams and auth kwargs, and **F3** touched T2/T11. The **merge-blocking** problem, however, was **T4 narrative / Surface 7** (**F1**), i.e. **trouble came materially from the doc-and-decision-log coupling** the adversarial table had already **flagged as confirmed**, not from LiteLLM response-shape replanning.
- **§5.4 hidden couplings:** **Surface 7** (T7/T9 stale vs code) **mattered decisively** — it became **F1**. **Lazy `litellm` import** (**suspected** → **disproven** for import-time side effects) matched audit **O2** / cold-read **C1**. **Pipeline `HecklerConfig(anthropic_api_key=...)`** stayed valid (**O1**).

## 5. Methodology gaps surfaced

- **Orchestrator / plan:** **T4** scope said errata **or** fencing **must not** leave false current behavior; the **gap** was not missing text in the plan but **insufficient downstream enforcement** of that kill criterion before “done.” Consider stronger explicit **definition of done** for decision logs (e.g. top-to-bottom scan rule, or auditor gate **before** marking T4 complete).
- **Executor skill / practice:** A **standard** subtask with **document truth** kill criteria behaved like “append Landed bullets = fixed” while leaving **scan-visible** stale blocks — that is the kind of slip the executor HALT rubric is meant to catch if the executor treats kill criteria as **order-sensitive prose**, not only **new** paragraphs.
- **Contracts schema:** **§2** shortest wording lagged **code** on **`azure/`** until v1.2 *Landed* — a real **contract vs implementation** lag window; **T11** as named authority for extensions helped close it in **T5** (re-audit **F3 resolved**).
- **Pre-plan / scout:** Audit **S1** (grep set missing post-migration tokens) aligns with context-map drawn **pre-migration** — feedback for **pre-plan-exploration** iteration, not a task failure.
- **Auditor skill:** Phase 0 **narrative isolation** was **partial** per audit v1.1 §3 — **nothing notable** as fatal; **F1** still fired on v1.1. **v1.2** added an **omission-free artifact checklist** (plan, packets, T7–T11, code, README, CHANGELOG, pytest) — positive signal that **re-audit** can **systematically** close a failed gate without scope creep.
- **Residual after `pass`:** **S1** remains **open (process)** / observation-grade in the audit; **`azure/`** auth still **no dedicated unit test** (minor gap, documented in T11/README) — not methodology failures, but honest tail on the audit record.

## 6. Single sentence verdict

**Partially** — first-pass **T4** discipline and **T5** packet-order hygiene still read as **methodology leaks**, but **audit v1.2 (`pass`)** shows the **fail → amendment → re-audit** loop **closed F1–F3** and restored **merge-ready** narrative/code alignment without a further replan.

---

## 7. Changelog (this retro)

| Retro ver | When | What changed |
|-----------|------|----------------|
| **0.1** | Initial file | Reflects audit **v1.1** `fail`, **T5** plan/process notes, no re-audit outcome. |
| **0.2** | After audit **v1.2** | Bumped after **`pass`**; §1/§3/§5/§6 updated; **S1** + **azure/** test gap noted as post-pass residuals. |
