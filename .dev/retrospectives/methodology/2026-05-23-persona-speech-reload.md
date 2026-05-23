# Retrospective — methodology — persona-speech-reload (deep pass)

**Date:** 2026-05-23  
**Plan:** `.dev/plans/persona-speech-reload/plan.md` **v1.1.0**  
**Context map:** pre-plan-exploration **v0.2** @ scout `80c60a0ea5d1008d2c9f57d17520ada7ea9f6aac` (CONDITIONAL)  
**Audits:** `.dev/audits/2026-05-22-persona-speech-reload.md` — **initial cold audit only**, verdict **`pass-with-conditions`** @ `a5e5b96a2420cc3eab85f12c876589e2be9a8d83` (no re-audit, no amendment subtask)  
**Binding spec:** `PERSONA_SPEECH_RELOAD.md` (tracked @ T1 `ae491c43`)  
**Prior plan superseded:** `locale-lang-propagation` (FIND-A6 closed via T8 addendum)

**One line — what the task was:** Third/final locale fix — conditional Whisper/Kokoro reload when `(whisper_language, kokoro_lang_code)` changes; GUI locale override combo + unified `_apply_persona_and_speech`; `ModelLoadThread` reads combo at `run()`; CLI `ensure_heavy_models` as sole startup load; scenario matrix + supersession of “swap never rebuilds.”

**Artifacts read:** `plan.md` §0–§8, `context-map.md`, packets **T1–T8**, `PERSONA_SPEECH_RELOAD.md` (sampled §structure), decision logs **persona-speech-reload-T2/T4**, superseded **locale-lang-propagation-T4/T7**, `CHANGELOG.MD` persona slice, `.dev/audits/2026-05-22-persona-speech-reload.md`, locale-lang audit FIND-A6 addendum, git log `ae491c43` → `a5e5b96a`, spot-checks on `controller.py`, `main_window.py`, `pipeline.py`, tests.

---

## 1. Task identifier

| Field | Value |
|-------|--------|
| **Name** | persona-speech-reload |
| **Execution window** | 2026-05-22 (T1–T8 + plan bundle commit) |
| **Plan version** | **1.1.0** — §8 orchestrator handoff @ closure `31228054`; plan/packets committed @ `a5e5b96a` |
| **Orchestrator** | orchestrator-planning **v0.6** |
| **Executor** | Full contract-first DAG, eight packets, adversarial §5 |
| **Log tiers** | **T2**, **T4** → `architectural`; **T1**, **T3**, **T5**, **T6**, **T7** → `standard`; **T8** → `trivial` |

### Implementation commit chain

| Subtask | Commit | Message (abbrev.) |
|---------|--------|-------------------|
| T1 | `ae491c43` | `speech_stack_signature`, `supported_locale_labels`, track spec |
| T2 | `87549218` | Controller reload API |
| T3 | `4b149019` | GUI locale combo |
| T4 | `c1861894` | ModelLoadThread callables, F1/F2 |
| T5 | `964f020c` | `_apply_persona_and_speech`, ask dialog, `_ReloadThread` |
| T6 | `78c945bf` | CLI `ensure_heavy_models` sole startup load |
| T7 | `2d924cdc` | Scenario matrix, README, persona_builder |
| T8 | `31228054` | Decision log polish, FIND-A6 addendum |
| Bundle | `a5e5b96a` | `plan.md` + packets + transcript stubs |

---

## 2. Plan vs reality

### DAG vs execution

**Dependency shape held.** No re-plan, no audit-driven amendment subtask (contrast `gui-launcher` T5, `locale-lang-propagation` T7/T8, `persona-system` T7).

| Planned | Actual | Assessment |
|---------|--------|------------|
| T1 → T2 → {T3,T6} parallel | T3 @ `4b149019`, T6 @ `78c945bf` **after** T5 | T6 only needs T2 — **late but safe**. Missed parallel window with T3/T4; process inefficiency only. |
| T3 → T4 (merge-risk sequence) | T4 immediately after T3 | **Correct** — single `main_window.py` owner chain. |
| T4 → T5 | T5 after T4 | **Correct** |
| T2,T3,T4,T5,T6 → T7 | T7 after T6 | **Correct** |
| T7 → T8 | T8 after T7 | **Correct** |

**Parallel group `{T3, T6}` after T2:** Not exercised. Would have been safe (disjoint files). Sequencing T3→T4→T5 before T6 did not violate DAG edges.

**Cross-plan relationship:** Same-day predecessor `locale-lang-propagation` landed the locale module and “swap never rebuilds” decision logs; this plan **explicitly superseded** those semantics. Context map Flag 4 (artifact tree vs spec-only) resolved by user requesting full orchestrator plan — no collision.

### Contracts at implementation surface (§2)

**Held** for every named §2 symbol at audit HEAD — audit Phase 2 **Pass** on types, sentinel, error envelope, logging literals, CLI surface, mandatory test replacement.

| Area | Verdict | Notes |
|------|---------|-------|
| 13 §2 type rows | Implemented + tests | Audit §8.3 table; spot-check `speech_stack_signature`, reload API, GUI apply path |
| Sentinel `None` vs `"From persona"` | Enforced | `selected_locale_override`, `test_target_speech_config_empty_locale_override_ignored` |
| `swap_persona` same-sig only | Docstring + body | **No runtime signature guard** — contract is caller responsibility (audit PSR-04 / CR-02); not a hollow §2 row but a **documented sharp edge** |
| Scenario S1–S14 | Mock-level in T7 | Spec §20 real-model boot **deferred** — acknowledged in CHANGELOG + audit PSR-02 |
| Mandatory old test removal | Done | `test_swap_persona_does_not_change_transcriber_whisper_language` absent |

**Not hollow:** `SpeechReloadPolicy` is a real enum; reload predicate uses `speech_stack_signature` on resolved config, not `getattr` defaults.

**Residual coverage (accepted, not §2 violations):** locale-combo-only change while running (PSR-03); direct `swap_persona` after cross-locale load without reload (by design); circular-import kill criterion for T1 mitigated by `TYPE_CHECKING` but not pytest-exercised (CHANGELOG deferral).

### §2 / decision-log narrative survival

| Drift | Repair |
|-------|--------|
| `locale-lang-propagation-T4.md` body still describes Reactor-only swap | **T2** — top supersession banner; audit Phase 3 **Pass** |
| `locale-lang-propagation-T7.md` init-time `config.persona_name` | **T4** — supersession banner |
| `persona-speech-reload-T2/T4` drafted in architectural subtasks | **T8** — trimmed/finalized @ `31228054` (not stale pre-amendment prose) |
| `locale-lang-propagation` plan §8.3 still cites old swap test as evidence | **Not repaired** in that archived plan — superseded by FIND-A6 addendum in **its** audit file |

No narrative-concealment finding; CHANGELOG “Deferred (adversarial §2.1)” bullets align with audit coverage gaps.

### Log tiers

| Subtask | Tier | Calibration |
|---------|------|-------------|
| T2 | architectural | **Appropriate** — new public API, supersedes landed log, real forks in spec §16 |
| T4 | architectural | **Appropriate** — threading ownership, callable vs window reference |
| T5 | standard | **Arguably under-tiered** — plan §5.3 named T5 **highest re-plan risk** (GUI-thread blocking, QThread offload). Landed cleanly via `_ReloadThread`, but tier label understates blast radius if offload had failed |
| T8 | trivial | **Appropriate** for doc-only delta, but **scope overlap** with T2/T4 decision-log writes — see §3 |

### Closure vs committed reality

| Check | Result |
|-------|--------|
| §8.1 closure SHA `31228054` = first commit with T8 outputs? | **Yes** for code + decision-log polish + FIND-A6 addendum |
| Plan + packets in closure SHA? | **No** — plan §8.2 flagged **absent-from-HEAD**; remediated @ `a5e5b96a` (same pattern as `persona-system`, `locale-lang-propagation`, `gui-launcher`) |
| Audit ran on merge-target tree? | **Yes** — audit HEAD `a5e5b96a` includes plan bundle; working tree **clean** |
| Context map SHA vs audit HEAD | **Diverged** (PSR-P01) — expected; stale-qualified, not a code defect |
| CHANGELOG complete for T1–T8? | **No** — **T6 CLI slice missing** from persona-speech-reload section (plan §8.2 notes omission; land evidence @ `78c945bf`) |
| §8.1 pytest **349 passed** | Claimed @ orchestrator re-run; auditor ran **167** in contract subset, full `pytest tests/ -m "not heavy"` **not re-run to completion** in audit environment (PSR + audit §1) — same verification gap as sibling retros |

**Drift caught:** plan §8.2 documented absent plan/packets before archaeology commit; audit PSR-P02. **Latent until audit:** T6 CHANGELOG gap (audit did not file as finding).

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Zero HALTs** recorded in packets, CHANGELOG, or commit messages. All eight subtasks landed in one forward pass.

**Kill criteria as silent gates:** No evidence of kill criteria being “satisfied” by narrative while code still violated (e.g. old swap test removed only in T7 as planned, not early). T7 correctly **blocked** completion until mandatory test deletion — by design, not a late surprise.

**HALT-shaped improvisation not escalated:**

- T6 could have double-called `load_models` + `ensure_heavy_models`; executor chose plan **option 1** (sole `ensure_heavy_models`) — matches packet kill criterion, not improvisation.
- T5 `_ReloadThread` was **planned** mitigation for §5.2 assumption #4 — not an undisclosed scope expansion.

### Amendment cycles

**None.** Audit verdict `pass-with-conditions` with observations only (PSR-01–03, PSR-P01–02). No T9-shaped remediation, no plan v1.2, no re-audit.

**First-pass cleanliness:** Code/contracts **genuinely clean** on adversarial axes the audit exercised. Weakness is **verification depth** (manual S1–S3, subset pytest), not missed amendment. Contrast `locale-lang-propagation`, which needed amendment after audit failure.

**T8 vs amendment:** T8 is **closure hygiene** (decision log edit, audit addendum), not audit remediation — appropriate tier `trivial`.

---

## 4. Adversarial pass calibration

### Rejected alternatives that mattered later

| Alternative | Outcome |
|-------------|---------|
| **A — full dispatch inside `swap_persona`** | Rejection **held**. GUI owns dialog, revert, `_ReloadThread`; controller stays primitive. No re-plan pressure to move dialog into controller. |
| **B — merge T3+T4** | Rejection **held**. Sequential T3→T4 avoided `main_window.py` conflicts; no merge incident in git history. |
| **C — explicit `load_models` + redundant `ensure_heavy_models` on CLI** | **Selected opposite** (sole `ensure_heavy_models`) — landed @ T6; kill criterion prevented double-load. |

### Load-bearing assumptions

| # | Assumption | Held? |
|---|------------|-------|
| 1 | `HecklerConfig` safe for `replace()` | **Yes** — target_speech_config tests |
| 2 | No circular import locale↔controller | **Yes** — full suite green @ plan time |
| 3 | `load_persona` callable when combo lists persona | **Mostly** — GUI catches missing dir; not exhaustive integration test (plan: treat-as-prediction) |
| 4 | Reload must not block GUI thread 30–60s | **Yes** — `_ReloadThread`; **this was the critical fork**; failure would have triggered §5.3 re-plan |
| 5 | Old swap test sole encoder of retired contract | **Yes** — removed T7 |
| 6 | `heckler_arg` already `ef_dora` | **Yes** |
| 7 | No string-literal `SpeechReloadPolicy` misuse | **Yes** — `str, Enum` + policy test |

### Highest re-plan risk (T5) vs actual trouble

**Plan named T5.** Trouble **did not** materialize as re-plan: `_ReloadThread` pattern landed in T5 commit without DAG change. Process risk (T3/T4/T5 all touch `main_window.py`) was **mitigated by sequencing**, not parallel execution.

**Trouble came from elsewhere (process, not architecture):**

- **Archaeology commit hygiene** (`a5e5b96a`): `GUI_DARK_THEME.md` + 13 one-line `transcripts/*.md` outside plan §4 (audit PSR-01) — same class as other plans’ bundle commits.
- **CHANGELOG T6 omission** — documentation chain gap, not runtime.
- **Plan/packets absent @ implementation closure SHA** — recurring methodology debt until `a5e5b96a`.

---

## 5. Methodology gaps surfaced

**Orchestrator skill should have prompted for:**

- **CHANGELOG row per landed subtask** — T6 has a commit and tests but **no bullet** in persona-speech-reload section (plan §8.2 caught it for handoff, not CHANGELOG template).
- **Bundle commit scope guard** — flag non-plan files (`GUI_DARK_THEME.md`, transcript stubs) before single archaeology commit, or split commits (persona-system / gui-launcher show same pattern).
- **Closure SHA discipline** — either commit plan bundle **in T8 commit** or set §8.1 SHA to `a5e5b96a` after bundle lands; reduces PSR-P02 class findings.

**Executor skill let through (minor, not blockers):**

- T8 “write decision logs” when T2/T4 already wrote them — **duplicate work** but T8 kill criteria (supersession consistency, FIND-A6 citation) still added value.
- No HALT when full-tree pytest count differed from packet verification command — acceptable if subtask scope used targeted modules.

**Contracts schema:**

- nothing notable — §2 table, sentinel rule, error envelope, and decision-log paths worked well for audit Phase 2.
- **Optional:** explicit §2 row for “runtime enforcement optional” APIs (`swap_persona`) vs “must enforce” — would have made PSR-04 a contract row instead of observation.

**Audit skill:**

- Subset pytest + hung full suite → **conditions** list already recommends local 349 re-run; methodology should treat “plan §8.1 count unverified” as a **standard audit checklist item** when environment blocks full run.

**Do not edit skills here** — patterns align with `gui-launcher`, `persona-system`, `locale-lang-propagation` retrospectives (bundle SHA drift, CHANGELOG gaps, archaeology scope).

---

## 6. Single sentence verdict

**Partially yes** — the orchestrator/executor process delivered a coherent DAG, enforced §2 contracts with real tests, superseded prior decision logs correctly, and avoided re-plan on the highest-risk subtask (T5), but **recurring closure hygiene** (plan absent @ T8 SHA, T6 missing from CHANGELOG, unrelated files in bundle commit) and **unverified full-suite pytest** show the methodology **leaked on artifact chain completeness**, not on implementation architecture.
