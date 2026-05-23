# Retrospective — methodology · transcription-engine (deep)

**Date:** 2026-05-23 (re-read of 2026-05-16 execution)  
**Plan:** `.dev/archive/transcription-engine/plan.md` **v1.1** (orchestrator-planning **v0.6**; amendment **T6**)  
**Context map:** pre-plan-exploration **v0.2** @ scout `7b5382e…` → map **v1.1** with §Phase 0.5 reflexive baseline  
**Audits:** `.dev/audits/2026-05-16-transcription-engine.md` rev **1** → **fail** (P1–P3); rev **2** → **`pass`** @ `026d68d6dfd3507f7c4debf93a1cf94ad6ea0239`  
**Prior methodology note:** `.dev/retrospectives/methodology/2026-05-16-transcription-engine.md` (contemporaneous, shorter)  
**One line:** Standalone `--mode transcribe` (store + config + pipeline + tests) landed correctly in code, but **orchestrator §8 closure failed once**, was repaired by **T6** at `026d68d`, then **post-archive path moves** re-broke the §8.2 path literals unless readers use the archive prefix or the bundle SHA.

---

## 1. Task identifier

| Field | Value |
|-------|--------|
| **Task** | `transcription-engine` |
| **Plan versions** | v1.0 (invalid §8) → v1.1 (+ **T6** remediation) |
| **Skills** | pre-plan-exploration v0.2, orchestrator-planning v0.6, executor-subtask-execution (implicit), auditor-review v0.4 |
| **Scope** | Transcribe-only pipeline: `transcript_store`, config/VAD fields, `pipeline` mode split + CLI, markdown export, integration tests; **not** PyQt6 GUI (Flag 3 deferred) |

**Artifact locations today:** Plan tree lives under **`.dev/archive/transcription-engine/`** (moved in `bb7746aa`). At **T6 closure** (`026d68d`) it lived under **`.dev/plans/transcription-engine/`**. Decision logs remain **`.dev/decision-logs/TE-T1.md`**, **`TE-T4.md`**. Audit is tracked at **`.dev/audits/2026-05-16-transcription-engine.md`** (first committed in `dcc28d71`, not at re-audit `HEAD`).

---

## 2. Plan vs reality

### 2.1 DAG vs actual execution

**Declared DAG:** `T1→T2`, `T1→T4`, `T3→T4`, `T4→T5`, `T5→T6`.

**Git-anchored implementation order (transcription-engine commits only):**

| Step | Commit | Message |
|------|--------|---------|
| T1 | `8439bb83` | transcript SQLite store module |
| T2 | `781c2aeb` | export_session_markdown |
| T3 | `ccc8560c` | transcribe config + tests |
| T4 | `9b94ff35` | transcribe-only pipeline + CLI |
| T5 | `1f601c19` | transcribe pipeline integration tests |
| T6 | `026d68d6` | track plan artifacts + auditor handoff |

**Parallelism:** **T1** and **T3** were safe to parallelize (disjoint files). History shows **persona-system** commits interleaved between transcription commits on the same branch (`b943195`, `809ba45`, `d8e25594`, etc.) — not unsafe for TE because files differ, but it explains why **v1.0 §8.1 cited `809ba45`** (a **persona-system T6** commit) while claiming the transcription plan bundle existed there (**P2**).

**Soft dependency T2 before T4:** Honored (`781c2aeb` before `9b94ff35`). No evidence T4 shipped without exporter.

**Amendment T6:** Correctly sequenced after T5; no second amendment loop after rev **2** `pass`.

### 2.2 Contracts at the implementation surface

Plan **§8.3** is an unusually strong contract matrix: each §2 symbol maps to a symbol site and a named pytest. Re-audit **202 passed** at `026d68d` on full `tests/`.

**Re-verified at current workspace `HEAD` (`adcbec9b`, 2026-05-23):** targeted transcribe tests **68 passed** (`test_transcript_store`, `test_config`, transcribe-related `test_pipeline`).

| §2 area | Enforced in code + tests? | Notes |
|---------|---------------------------|--------|
| `transcript_store` API + DDL | **Yes** | Dedicated `tests/test_transcript_store.py`; no FK to `events` |
| `HecklerConfig` transcribe fields + env | **Yes** | `tests/test_config.py`; **F4**: invalid non-empty `HECKLER_MODE` via env **not** validated — **waived** in CHANGELOG / audit **G1** |
| `_run_transcribe_worker`, CLI `--mode` / `--session-name` | **Yes** | Multiple `test_pipeline` falsifiers including Speaker/Reactor non-construction |
| Error envelope (`RuntimeError` on schema version, export paths) | **Yes** | Store tests + export missing-session tests |
| Logging contract | **Partial** | Structured logging in store; **`[TRANSCRIBE]` prints** in pipeline — documented (**F5**), not structured fields |
| Persona `_run_transcription_worker` direct tests | **Out of scope** | Plan Flag 5 — only transcribe worker path required |

**Hollow-contract check:** No evidence of `getattr` defaults or dropped §2 keys on the shipped transcribe path. Waivers are **explicit** (F4, join timeout, persona worker), not silent.

### 2.3 §2 / decision-log narrative survival

| Artifact | Status |
|----------|--------|
| **TE-T1** | **Repaired.** Supersession banner + **Items deferred** names T2 exporter (**F1** / FIND-02 class). Header says plan **v1.1**. |
| **TE-T4** | **Drift.** Header still **“Plan: transcription-engine v1.0”**; body matches shipped behavior. T6 **Files to touch** excluded TE-T4; F4 deferral not duplicated there (CHANGELOG owns it). |
| **Plan §8.3 annex** | Line numbers anchored to pre-T6 implementation HEAD **`b943195`**; plan warns **treat-as-prediction** after moves — honest. |
| **Archived plan §8.2** | Still lists **`.dev/plans/transcription-engine/...`** paths. At **`HEAD`**, `git show HEAD:.dev/plans/transcription-engine/plan.md` **fails**; **`git show HEAD:.dev/archive/transcription-engine/plan.md` succeeds**. Narrative frozen at closure paths; **repository layout diverged** without plan amendment. |
| **CHANGELOG** | Still links **`.dev/plans/transcription-engine/plan.md`** — same latent path drift. |
| **`.dev/archive/transcription-engine/transcription-engine.md`** | Design doc header still says **“not yet implemented”** while code shipped — **FIND-02-class** stale prose in archive, not repaired in T6 scope. |

### 2.4 Log tiers

| Subtask | Tier | Assessment |
|---------|------|------------|
| T1 | architectural | Correct — new persistence contract + TE-T1 |
| T4 | architectural | Correct — mode split + TE-T4 |
| T2, T3, T5 | standard | Correct |
| T6 | standard | **Under-tiered relative to blast radius** — only subtask that could flip audit **fail→pass**; binding §8.2 / git index / map baseline. Worth **architectural** or explicit “provenance” tag in future. |

### 2.5 Closure vs committed reality

**Timeline:**

1. **Implementation landed** (T1–T5) with code/tests in git; plan bundle **untracked** at pre-remediation audit HEAD **`b943195`** (**P1**).
2. **v1.0 §8 “Complete”** cited tree **`809ba456`** and paths under `.dev/plans/transcription-engine/` — **`git show` fatal** for those paths at that SHA (**P2**). That SHA is a **persona-system** commit, not the transcription bundle introducer.
3. **Audit rev 1** → **fail** (P1–P3 majors; F1–F5 minors) — rev **1** text not in git history; recovered only via rev **2** §10 table and plan §8.0 retraction.
4. **T6 @ `026d68d`** — committed plan tree under **`.dev/plans/transcription-engine/`**, reflexive §8.1 rule, pytest **202 passed** on clean tree, TE-T1 supersession.
5. **Audit rev 2 @ `026d68d`** → **pass**; Phase 0.5 map baseline **match**; `git show HEAD:` for binding rows **1–3, 5–6** succeed at that SHA.
6. **Post-closure:** `bb7746aa` **R100** rename **plans → archive** for transcription-engine (and persona-system, gui-launcher). Bundle content unchanged; **§8.2 path literals obsolete** at later `HEAD` unless updated or read at `026d68d`.
7. **`dcc28d71`** — first git commit of audit file (rev **2** body); plan §8.2 item **4** had allowed audit untracked at re-audit time — **G3** resolved for tracking later, not at `026d68d`.

**First audit tree state:** Re-audit used committed **`HEAD`**, not dirty-only plan copies — correct discipline once T6 landed.

**Context map pinned SHA:** Reflexive rule (`git log -1 --format=%H -- …/context-map.md`) **held** at `026d68d`. Scout `7b5382e` correctly demoted to **historical** in map §Phase 0.5 (**P3** superseded, not ignored).

---

## 3. HALTs and amendment cycles

### 3.1 Executor HALTs

- **No HALT transcripts** in archive packets, decision logs, or CHANGELOG.
- Kill criteria were **defined** on every subtask (T1–T6); none triggered in recorded artifacts.
- **Cannot rule out** chat-level HALTs from agent sessions.

**Interpretation:** Executors proceeded through T1–T5 without formal HALT — consistent with kill criteria never binding (no FK to events, no `event_store` schema change, frozen dataclass held, etc.).

### 3.2 Amendment cycles

| Cycle | Trigger | Scope | Outcome |
|-------|---------|-------|---------|
| **T6 (v1.1)** | Audit rev **1** P1–P3 (+ F1 hygiene; optional F4) | Git-index plan bundle, map baseline, §8 rewrite, TE-T1 banner, CHANGELOG | **Single pass** → rev **2** **pass** |
| **F4** | Invalid env-only `HECKLER_MODE` | — | **Deferred** with visibility (not silent) |

**Amendment scope discipline:** T6 did **not** re-open T1–T5 runtime code (except optional F4 test — not taken). **Retired-string sweep** claimed in plan; **TE-T4 v1.0 header** and **archive design doc “not implemented”** remain as residual narrative debt.

### 3.3 HALT-shaped improvisation (the real failure mode)

**v1.0 “Complete” without §8.2 object graph** is the inverse of executor over-halting:

- Green pytest + merged **code** were treated as sufficient.
- **Orchestrator §8.2** (`git show HEAD:<path>`) was **not** satisfied before the Complete banner.
- Kill criterion **(4)** on T6 packet literally encodes the fix: halt if `git show HEAD:.dev/plans/.../plan.md` fails after handoff — that criterion existed **because** v1.0 violated it.

**Cross-plan pattern:** Persona-system audit **FIND-01/FIND-02** (stale map, stale deferred prose) **predicted** TE failures; T6 imported the remediation **shape** after TE’s own audit fail — good reuse, **reactive** not preventive.

---

## 4. Adversarial pass calibration

### 4.1 Rejected decompositions (§5.1)

| Alternative | Verdict in hindsight |
|-------------|---------------------|
| **A — Monolith** | Rejection **held**. T1 architectural log + isolated store module paid off in audit §8.3 row-level traceability. |
| **B — Split CLI from T4** | Rejection **held**. Single `pipeline.py` owner for argparse + dispatch avoided hidden coupling. |
| **C — transcript_store inside event_store** | Rejection **held**. No `SCHEMA_VERSION` coupling; T1 kill criteria never fired. |

Nothing suggests a rejected alternative would have **prevented** the §8 leak (process failure, not decomposition).

### 4.2 Load-bearing assumptions (§5.2)

All six closed in plan **§8.4** and audit Phase 4 — **held** for the shipped slice:

1. Frozen dataclass + additive fields — pytest-backed.  
2. `threading.Event` for `is_playing` — stub/falsifier tests.  
3. `open_store` reuse — transcribe path uses it; dual init in one `main()` **does not run** today (theoretical hybrid risk noted).  
4. CLI supersession of prior plan — landed; no repo merge gate blocked.  
5. Import vs construction for heavy models — **construction-time** loading; transcribe branch skips construction.  
6. **§8.2 tracked paths** — **failed at v1.0**, **closed at T6**, **path literals stale after archive move** (assumption holds **at `026d68d`**, not at arbitrary future `HEAD` without path update).

### 4.3 Highest re-plan risk (§5.3)

| Predicted risk | Actual outcome |
|----------------|----------------|
| **T6** — policy forbids committing `.dev/plans/**` | **Did not block.** Scoped `git add` succeeded. |
| **T4** — VAD `replace`, import graph, integration | **Did not dominate audit.** Cold-read notes join/export semantics deferred, not blockers. |
| **Unpredicted** | **§8 / provenance** dominated until T6; **wrong SHA in v1.0** (persona commit id). |

### 4.4 Hidden couplings (§5.4)

All four dispositions in **§8.4** remain credible:

- Shared SQLite file — no concurrent dual-init in transcribe `main()`.  
- `config.mode` only in `pipeline.py` — grep-confirmed at audit time.  
- `--mode` string coupling T4→T5 — intentional, tested.  
- `_put_drop_oldest` enqueue-only — transcribe worker drains only.

**Post-hoc coupling (not in §5.4):** **CHANGELOG / §8.2 / T6 packet** still name `.dev/plans/...` while archive layout is canonical — documentation coupling to **directory convention**, not runtime.

---

## 5. Methodology gaps surfaced

### 5.1 Orchestrator / §8

- **§8 Complete must imply `git ls-files` + `git show` matrix** on the **cited SHA** before any Complete banner — v1.0 violated this; skill text was right, execution was not.
- **Reflexive §8.1** (bundle introducer via `git log -1 --format=%H -- <plan path>`) is the right fix for **P2** — should be **default**, not amendment-only.
- **Path stability:** No prompt to update §8.2 / CHANGELOG when plans move to **`.dev/archive/`** — closure truth at `026d68d` **decays** at `bb7746aa` for readers who run checks against `HEAD` without detaching.
- **Cross-plan FIND-01/02** should trigger **pre-audit** checklist on any plan claiming Complete, not only after fail.

### 5.2 Executor

- nothing notable — kill criteria appear respected; no scope violations in audit majors post-T6.
- **T6 could have normalized TE-T4 header** — in scope for “decision-log hygiene” spirit but not in Files to touch.

### 5.3 Auditor

- Rev **1** not in git — **audit revision archaeology** depends on rev **2** §10 or local IDE history (**G3**-class for process, not runtime).
- Re-audit **omission-free checklist** (rev **2** metadata) is a **good pattern** — compensated for weak first-pass closure signal.

### 5.4 Contracts schema

- nothing notable missing in §2 — gap was **indexing, SHA honesty, and path literals**, not missing rows.
- **Optional:** §8.2 row type for **“relocatable archive path + canonical SHA”** when plans leave `.dev/plans/`.

*(Per skill: do not edit orchestrator/executor/auditor skills from this file.)*

---

## 6. Single sentence verdict

**Partially** — the DAG, typed §2 contracts, pytest evidence, and adversarial §5 disposition **held** once code landed and **T6** restored a valid §8 object graph at **`026d68d`**, but **v1.0 §8 was process-invalid**, **T6 was under-tiered**, and **post-archive path moves reintroduced §8.2 literal drift at current `HEAD`** without a plan amendment, so the methodology **did not fully hold** on first closure and is **only locally complete** when pinned to the bundle introducer commit or updated paths.

---

## Appendix — evidence commands (2026-05-23)

```text
# Bundle introducer (T6)
git log -1 --format=%H -- .dev/plans/transcription-engine/plan.md  # => 026d68d6... at that commit

# Path drift at HEAD
git show HEAD:.dev/plans/transcription-engine/plan.md   # fatal
git show HEAD:.dev/archive/transcription-engine/plan.md # ok

# Archive move
git diff --name-status 026d68d6..bb7746aa -- .dev/plans/transcription-engine .dev/archive/transcription-engine

# Transcribe-focused tests at HEAD
python -m pytest tests/test_transcript_store.py tests/test_config.py tests/test_pipeline.py -q
```
