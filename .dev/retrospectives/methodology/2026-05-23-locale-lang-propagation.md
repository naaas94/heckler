# Retrospective — methodology — locale-lang-propagation

**Date:** 2026-05-23  
**Plan:** `.dev/plans/locale-lang-propagation/plan.md` **v1.0 → v1.3.0** (orchestrator-planning **v0.6**; amendment **v1.2.0** T6–T8)  
**Context map:** pre-plan-exploration **v0.2** @ scout `56c3748e99ea84bb6fa398bbaf474e0508918a99` (plan §0 notes stale vs planning `692dfa0`)  
**Audits:** `.dev/audits/2026-05-22-locale-lang-propagation.md` — rev **1 `fail`** @ `d0ce6d0`, rev **2 `pass`** @ `24ca9bd8` (audit file **not** in `24ca9bd8`; tracked later @ `31228054` via persona-speech-reload T8)  
**Closure SHA (code + plan v1.2.0 §8):** `24ca9bd8585a2b7952f5352117d0ba5cc39ba1a9`  
**Artifacts read:** `plan.md` §0–§8, `context-map.md`, packets **T1–T8**, decision logs **T1/T4/T7**, CHANGELOG `locale-lang-propagation` section, audit rev 1+2, `git log` `f1cb9a14`→`24ca9bd8`, spot-check code @ closure SHA and current `HEAD` (post–persona-speech-reload supersession).

**One line — what the task was:** Add a unified `HecklerConfig.locale` knob (`HECKLER_LOCALE` + persona `[voice].locale`) that resolves to Whisper and Kokoro language codes, wire `Speaker` off config, bake locale into heavy models at `load_models`, document that persona hot-swap does not change STT/TTS without reload, then amend CLI/GUI entry points after audit found propagation gaps.

---

## 1. Task identifier

- **Name:** locale-lang-propagation  
- **Dates:** scout **2026-05-17**; execution **2026-05-22**; audit rev 1+2 **2026-05-22**; methodology retro **2026-05-23**  
- **Plan versions:** **1.0** (T1–T5), **1.1.0** (working-tree §8 — audit fail), **1.2.0** (amendment T6–T8 @ `03c779e7`+), **1.3.0** (§8.1 SHA-align prose — **on disk, unstaged** vs committed v1.2.0 @ `24ca9bd8`)  
- **Log tiers:** architectural **T1**, **T4**; standard **T2**, **T3**, **T5**, **T6**, **T7**, **T8**

---

## 2. Plan vs reality

### DAG vs execution

| Planned | Actual (`git log`) | Assessment |
|---------|-------------------|------------|
| T1 → {T2 ∥ T3} → T4 → T5 | `f1cb9a14` → `02f8b58a` T2 → `680ca30e` T3 → `093ce56f` T4 → `d0ce6d0e` T5 | **Matched** dependencies; parallel group **not used** (sequential T2 then T3) — safe, no file overlap issue. |
| T5 → {T6 ∥ T7} → T8 | `344ca19d` T7 → `4739b325` T6 → `03c779e7`+ T8 (×4 commits for SHA align → `24ca9bd8`) | **Matched** amendment DAG; T8 **over-committed** (closure archaeology churn: `03c779e7`, `776c7969`, `b0483452`, `24ca9bd8`). |
| T4 highest re-plan risk | Controller API landed cleanly; **trouble was CLI/GUI callers**, not `controller.py` | Risk call **directionally right** (integration seam), **wrong layer** in mitigation (packet scoped controller only). |

**Unsafe parallelization:** nothing notable.

### Contracts at the implementation surface (§2)

**Held with code + tests (module / controller layer):**

| §2 anchor | Shipped | Proof |
|-----------|---------|-------|
| `heckler/locale.py` + `SUPPORTED_LOCALES` | Yes | `tests/test_locale.py` |
| `HecklerConfig.locale` / `kokoro_lang_code` / `apply_resolved_locale` / `HECKLER_LOCALE` | Yes | `tests/test_config.py`, `tests/test_locale.py` |
| `Speaker` → `config.kokoro_lang_code` | Yes | `tests/test_speaker.py` |
| Persona `[voice].locale` + re-resolve | Yes | `tests/test_persona.py` |
| `load_models(persona_name=...)` bake | Yes **when caller passes `persona_name`** | `tests/test_controller.py` |
| `swap_persona` no STT/TTS rebuild (v1 contract) | Yes @ closure | `test_swap_persona_does_not_change_transcriber_whisper_language` |
| `UnsupportedLocaleError` fail-fast | Yes | config + locale tests |

**Hollow / split contract until amendment (integration seam):**

| §2 intent | Gap @ `d0ce6d0` | Symptom |
|-----------|-----------------|---------|
| Persona locale → STT/TTS on **default** CLI/GUI paths | `pipeline.py` / `gui/app.py` called `load_models` **without** `persona_name` | Controller API correct; **production paths wrong** — audit **FIND-04/05** |
| §5.4 Surface 1 “closed” | Plan §8.4 claimed **closed** at v1.1.0 | **Narrative-concealment** — audit **FIND-06** |

**Entry-point rows** were added in plan **v1.2.0 amendment** (§2 T6/T7), not in v1.0 §2 — the gap was **plannable** from context-map (`pipeline.py`, `gui/app.py` as adjacent callers) but omitted from initial DAG.

**Post-closure:** `persona-speech-reload` superseded T4/T7 decision logs (conditional reload, `ModelLoadThread` callables). That is **downstream product evolution**, not a v1 hollow test — but it shows the v1 “swap never rebuilds” operator contract was **incomplete** for real GUI/CLI use.

### §2 / decision-log narrative survival

| Artifact | Drift | Repaired? |
|----------|-------|-----------|
| Plan §8.4 Surface 1 **closed** @ v1.1.0 | **False** — CLI/GUI unwired | **Yes** — T8 + audit rev 2; §8.6 cross-link |
| T4 log: “operators must call `load_models(persona_name=...)`” | **True in API, false in `pipeline`/`gui`** until T6/T7 | **Partially** — code fixed; log never amended to “call sites wired in T6/T7” |
| T4/T7 logs: “swap never rebuilds” / frozen `config.persona_name` | **Superseded** by persona-speech-reload | Banners on logs @ later commit — **not** repaired inside locale task |
| Context map @ `56c3748` | Stale line inventory | **No** rescout — plan §0 + audit **FIND-01** treat-as-prediction |
| Plan v1.3.0 §8.1 @ `24ca9bd8` | Working tree ahead of closure commit | **Latent** — R2-01; non-blocking per re-audit |

### Log tiers

| Subtask | Tier | Calibration |
|---------|------|-------------|
| T1 | architectural | **Appropriate** — new module + config contract. |
| T4 | architectural | **Appropriate** — load-time bake + hot-swap semantics. |
| T2, T3 | standard | **Appropriate**. |
| T5 | standard | **Appropriate** — docs + track bundle; should not have been “complete” without entry-point check. |
| T6, T7 | standard | **Appropriate** for wire-only amendment; **under-planned at v1.0** — should have been in original DAG or explicit v1 deferral with §8.4 **open**. |
| T8 | standard | **Appropriate** — narrative/§8 only. |

### Closure vs committed reality

**Multi-layer leak (caught by audit, mostly repaired):**

1. **T5 @ `d0ce6d0`:** Code + tracked plan bundle + CHANGELOG landed; working-tree §8 populated but **not in SHA** — audit **FIND-02**.
2. **§8.1 “clean tree”:** Omitted modified `plan.md` — **FIND-03**.
3. **v1.1.0 “Complete” + §8.4 Surface 1 closed:** Integration paths still broken — **FIND-04/05/06**; verdict **`fail`**.
4. **Amendment closure @ `24ca9bd8`:** T6/T7 code + plan v1.2.0 §8 in SHA; **146** pytest; re-audit **`pass`**.
5. **Residual archaeology:** Plan **v1.3.0** still unstaged; audit markdown **absent from `24ca9bd8`** (added in git only after persona-speech-reload). First audit ran against correct **code** SHA but **stale/dirty** plan narrative — rev 2 ran @ `24ca9bd8` with same plan drift observation (R2-01).

**First commit containing all named runtime artifacts for v1 intent:** effectively **`4739b325`/`344ca19d`** (T6/T7), not `d0ce6d0` (T5). Plan’s own §8.1 chain documents this honestly **after** amendment.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Documented HALTs in packets, CHANGELOG, or decision logs:** **zero**.

**HALT-shaped gaps that were not escalated:**

| Signal | Where | Should have HALTed? |
|--------|-------|---------------------|
| T4 kill criterion 2: `load_models` must not pass raw config when persona locale diverges **and `persona_name` available at load** | Satisfied in `controller.py`; **violated** in `pipeline.py` / `gui/app.py` at `d0ce6d0` | **Yes** — integration gap or explicit plan amendment deferring CLI/GUI to v1.1 **before** marking T5 complete |
| T4 decision log assumption: callers must pass `persona_name` | No falsifier at `pipeline`/`gui` in T4 scope | Executor **improvised past** — “API done = task done” |
| Plan §8.4 Surface 1 **closed** without entry-point tests | T5 / orchestrator handoff | Orchestrator/executor treated controller unit tests as sufficient for **end-to-end** propagation |

No evidence of **false** HALTs (over-halting).

### Amendment cycles

| Wave | Trigger | Subtasks | Outcome |
|------|---------|----------|---------|
| **T6–T8** | Audit rev 1 **`fail`** (FIND-02–06) | T6 CLI, T7 GUI, T8 plan §8 + audit cross-link | **Closed** at rev 2 **`pass`** @ `24ca9bd8` — **one** amendment pass, no second code amendment |

**Amendment scope:** **Right** — wired existing call sites + kwargs tests; no locale picker, no swap rebuild (still non-goals). **Residual:** deferred FIND-07/08/09 (minor, logged in T1/T4/T5 + CHANGELOG).

**First-pass audit strength:** Rev 1 cold-read (CR-01/02) found P0 integration failures that **101** contract-module tests did not. Rev 2 adversarial A4/A5 **pass** — amendment tests are **kwargs capture**, not full E2E Whisper-language assertions (accepted deferral in T6/T7 logs).

**Architectural-tier task with amendment:** First pass was **not** genuinely clean; audit was **not** too weak — it was **necessary**.

---

## 4. Adversarial pass calibration

### Rejected alternatives (§5.1)

| Rejection | Still valid? |
|-----------|--------------|
| Split STT/TTS env knobs | **Yes** — unified `locale` held. |
| Rebuild on every `swap_persona` | **Partially** — rejected for v1; **persona-speech-reload** later added **conditional** rebuild — product corrected plan non-goal without invalidating locale resolver. |
| Six-way split | **Yes** — T2/T3 mechanical split was enough. |

### Load-bearing assumptions (§5.2)

| Assumption | Outcome |
|------------|---------|
| Unified locale maps to Whisper + Kokoro | **Held** |
| Kokoro accepts resolved codes | **Held** (mocked tests) |
| `apply_resolved_locale` after persona merge | **Held** in `persona.py` |
| Heavy models snapshot at `load_models` | **Held in controller**; **failed at CLI/GUI callers** until T6/T7 — assumption tuple was **incomplete** without “callers pass `persona_name`” |
| `swap_persona` no rebuild | **Held for v1**; later superseded downstream |
| `whisper_language` not env-direct | **Held** |
| LLM register prompt-only | **Held** |

### Highest re-plan risk (§5.3)

**T4 / GUI–CLI call order** — **correctly identified.** Trouble materialized as **missing `persona_name` at `load_models`**, not wrong bake inside controller. Mitigation in v1.0 plan **under-scoped** T4 to `controller.py` only; context-map Surface 1 already named `pipeline`/`controller` split.

### Hidden couplings (§5.4)

| Coupling | Planned | Actual |
|----------|---------|--------|
| Surface 1: Transcriber base vs merged worker cfg | **confirmed** | **Open** on CLI/GUI until T6/T7 — scout prediction **verified** |
| Speaker `lang_code="a"` | confirmed | **Closed** T2 |
| `load_config` language gap | confirmed | **Closed** T1 |
| `test_speaker` en-only assert | confirmed | **Closed** T2 |
| `test_controller` swap hides config | suspected | **Ruled out** T4 — good falsifier |
| `prompts/heckler` lacks locale | informational | Still true — operator must edit TOML |
| README English-only | informational | **Closed** T5 |

---

## 5. Methodology gaps surfaced

**Orchestrator skill should have prompted for:**

- **Entry-point subtasks in v1.0** when context-map lists `pipeline.py` and documents GUI `load_models` before persona pick (Flag 2 resolution still required **wiring**, not picker UI).
- **§2 row for Entry-point integration** up front, with falsifiers in T4 or T5 — not only after audit failure.
- **Explicit §8.4 disposition rules:** “controller API closed” ≠ “Surface 1 closed” until CLI/GUI tests pass.
- **Closure discipline:** forbid §8 “Complete” / Surface 1 **closed** on working tree while `plan.md` unstaged or integration tests absent.

**Executor skill should have blocked:**

- Marking T4/T5 done when T4 kill criterion 2 is only proven by **controller** tests while `pipeline.py` / `heckler/gui/app.py` remain in the integration blast radius (even if not in `files-to-touch` — contract drift / implied integration).
- Landing §8.4 **closed** without `tests/test_pipeline.py` / `tests/test_gui.py` `load_models` kwargs assertions.

**Contracts schema:**

- **Missing early:** `Entry-point integration` as first-class §2 topic (added only in amendment).
- **Vestigial:** nothing notable — `kokoro_lang_code` + derived `whisper_language` split is intentional.

**Auditor-review skill:**

- **Worked as designed** — Phase 0 cold read before §8 narrative caught FIND-04/05/06; rev 2 validated amendment without expanding scope.
- **Hygiene gap:** audit file not in closure SHA — plan §8.2 acknowledged but closure still claimed “audit cross-link” before file was tracked.

**Do not edit skills in this retro** — pattern: *integration seams need DAG rows and tests in the same wave as controller APIs when context-map flags them confirmed.*

---

## 6. Single sentence verdict

**Partially** — core resolver/config/controller contracts and adversarial audit did their job, but v1.0 allowed a **false-complete** closure (§8 + Surface 1) because integration call sites were omitted from the initial DAG and no executor HALT fired when unit tests green-lit a split STT/TTS path; amendment T6–T8 and rev 2 audit repaired product and narrative, while closure archaeology (unstaged v1.3.0, audit-not-in-SHA, T8 SHA churn) remained sloppy until a follow-on plan.
