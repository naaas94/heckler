# Retrospective — methodology — persona-system (deep pass)

**Date:** 2026-05-23  
**Plan:** `.dev/archive/persona-system/plan.md` — **v1.0 → v1.1** (T7 audit remediation)  
**Context map skill:** pre-plan-exploration **v0.2** (initial scout); T7 rescout regen at **`026d68d`**  
**Prior methodology note:** `.dev/retrospectives/methodology/2026-05-16-persona-system.md` (shorter pass at audit time)

**One line — what the task was:** Introduce swappable persona bundles (`prompts/<persona>/`), `heckler/persona.py`, config/env/CLI wiring, reactor refactor + `CommentType.UNKNOWN` fallback, migrate default prompts to `prompts/heckler/`, then close planning-hygiene audit findings (FIND-01–03) via **T7** without touching runtime code.

**Artifacts read (this pass):** archived `plan.md`, `context-map.md`, `persona-system.md`, packets **T1–T7**, `.dev/audits/2026-05-16-persona-system.md` (rev 3 at HEAD), `.dev/decision-logs/persona-system-T1.md`, `persona-system-T3.md`, `.dev/decision-logs/T7.md` (reactor), `CHANGELOG.MD` persona slice, git history for implementation + planning commits, current `HEAD` **`adcbec9b`** vs audit pin **`4e8f91f`**.

---

## 1. Task identifier

| Field | Value |
|-------|--------|
| **Name** | persona-system |
| **Execution window** | 2026-05-16 (implementation + audit loop); bundle archived 2026-05-22 (`bb7746aa`) |
| **Plan versions** | **1.0** — T1–T6 landed; v1.0 §8 handoff did not survive strict audit. **1.1** — T7 doc remediation + §0/§7/§8 refresh. |
| **Orchestrator / executor** | Full contract-first plan, seven executor packets, adversarial §5, amendment **T7** after audit. |
| **Log tiers** | **T1**, **T3** → `architectural`; **T2**, **T4**, **T5**, **T6**, **T7** → `standard`. |

### Implementation commit chain (code)

| Subtask | Commit (short) | Notes |
|---------|----------------|--------|
| T1 | `d5922a25` | `heckler/persona.py` + `tests/test_persona.py` |
| T2 | `d46423dc` | `git mv` to `prompts/heckler/` + `persona.toml` |
| T4 | `3967dc75` | `persona_name` / `HECKLER_PERSONA` (parallel with transcription-engine T4 on same day) |
| T5 | `d8e25594` | Pipeline wiring + `--persona` |
| T6 | `809ba456` | Examples path test + README packaging note |
| T7 (docs only) | `01f388e6` | Map regen, T3 log supersession, plan §0/§8, T2 packet — **did not** add `packets/T7.md` to git |
| T7 §8 pin | `4e8f91f4` | Plan §8 snapshot records T7 doc SHA only |

T3 reactor work is embedded in the T5/T6 window (no standalone `persona-system` T3 commit message); `persona-system-T3.md` and reactor diffs align with **`809ba45`** closure family.

---

## 2. Plan vs reality

### DAG vs execution

**Matches the planned shape.** `{T1, T2, T3, T4}` as parallel leaves → **T5** integrator → **T6** cross-cutting → audit failure → **T7** amendment (`T6 → T7`). No evidence that parallel file ownership was unsafe; the painful sequencing was **expected mid-DAG test breakage** (documented in `CHANGELOG.MD` T2 bullet: reactor still reading root `prompts/` until T3/T6), not a surprise merge conflict.

**Cross-plan concurrency (same calendar day):** Transcription-engine landed `mode`, transcribe CLI, and extra `HecklerConfig` fields while persona-system ran. Plan §5.4 #6 and audit cold-read correctly treated this as **observation**, not contract violation — persona load stays behind `mode != "transcribe"` guard. Methodology held: §2 stayed persona-scoped; concurrent plan fields were not falsely attributed to persona subtasks.

### Contracts at implementation surface (§2)

**Held** for every named runtime symbol at audit time and on spot-check today:

| §2 area | Verdict | Evidence |
|---------|---------|----------|
| 9 types/interfaces | Implemented | `heckler/persona.py`, `reactor.py`, `config.py`, `pipeline.py` |
| TOML mapping (9 rows) | Implemented | `_TOML_TO_CONFIG`; `[output].comment_types` skipped |
| Error envelope | Implemented | `PersonaNotFoundError`; UNKNOWN fallback + WARNING string |
| Logging (3 lines) | Implemented | Audit Phase 2 byte-match narrative |
| Named tests | Present | e.g. `test_invalid_comment_type_in_json_returns_unknown`, `test_main_persona_flag_*`, `test_load_config_persona_name_*` |
| CLI `--persona` | Implemented | `tests/test_pipeline.py` |

**Not hollow:** tests use real `tmp_path` bundles and pipeline integration paths; no `getattr` default shell for §2 symbols.

**Residual technical risk (plan §8 cold-read, not §2 violations):** `_flatten_persona_toml` passthrough of unmapped keys inside known sections; `[output]` keys other than `comment_types` — still valid observations, unchanged after T7.

### §2 / decision-log narrative survival

| Drift | Repair |
|-------|--------|
| `persona-system-T3.md` **Items deferred** read as current after T5 | **T7** — superseded block + **Landed** section (FIND-02) |
| `.dev/decision-logs/T7.md` root-`prompts/` assumption | **T3** — supersession banner at top (FIND-adjacent; §5.4 #5) |
| Plan §0 underplayed post-land map staleness | **T7** + v1.1 §0 **Staleness methodology** (FIND-01) |
| Plan §5.4 #1 evidence parenthetical still cites `Reactor(config)` | **Not repaired** — audit rev 3 **observation** only; disposition table already “resolved” |
| `.dev/persona-system.md` header “Design — not yet implemented” | **Not repaired** — informational doc rot |

### Log tiers

- **T1 / T3 architectural:** Appropriate — new module + reactor semantic + decision logs.
- **T7 standard:** Appropriate for docs-only work, but audit load-bearing; tier label understates **process gate** importance in hindsight.

### Closure vs committed reality

**Three-layer closure story** — methodology strength and weakness in one task:

1. **Runtime closure (`809ba45` family):** Real. Persona path works; audit rev 1 cold-read and pytest **202** at T7 time support this.

2. **v1.1 narrative closure (`01f388e6`):** FIND-01–03 remediated in **committed** map, plan, T3 log, T2 packet. Map baseline **`026d68d`** reflexive at regen time.

3. **Artifact-graph closure:** **Leaked twice.**
   - **FIND-ARCH-1 (rev 3):** Plan §6/§8 claimed `packets/T7.md` tracked; `01f388e6` never added it; file existed only in worktree until **`bb7746aa`** renamed `plans/…/T7.md` → `archive/…/T7.md` (pure rename, 0-line diff).
   - **Post-archive (current `HEAD` `adcbec9b`):** Bundle lives under `.dev/archive/persona-system/`; audit rev 3 still references `.dev/plans/persona-system/` and still **`fail`** on `git show HEAD:.dev/plans/persona-system/packets/T7.md`. **`git show HEAD:.dev/archive/persona-system/packets/T7.md`** succeeds. No audit **revision 4** after archive.

**Audit lineage gap:** Revision **2** (FIND-01/02/03 majors) is **not in git** — only summarized inside revision **3** (`dcc28d71` replaced revision **1** audit text). Methodology consumers cannot diff rev 2 prose; only rev 1 (`b943195b`) and rev 3 (`HEAD`) exist.

**First audit (rev 1, committed at `b943195b`):** Code-aligned cold-read; minors F1/F2 `artifact-not-in-HEAD` for unstaged plan/packets/T3 log; argued map **not** stale for *code* because only `.dev/` changed between `7b5382e` and landing SHAs. Stricter rev 2 (not committed) inverted that for **process**: nine §File map paths diverged → **FIND-01** `context-map-stale` — consistent with later v1.1 §0 rule once written down.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Zero documented HALTs** across packets, decision logs, and changelog. Kill criteria in T1–T7 were satisfied without executor escalation narratives.

**HALT-shaped behavior that was intentional, not escalated:**

- **T2 parallel window:** `tests/test_reactor.py` expected red until T3/T6 — packet explicitly says **not** a T2 halt condition; changelog records it. Correct use of planned DAG tolerance vs silent improvisation.
- **T7 optional `persona-system-T7.md` decision log:** Plan allowed omission; no HALT required.

**Nothing notable** suggesting kill criteria were “satisfied” in prose while scan-visible stale blocks remained — audit rev 3 re-checked map rows and T3 log.

### Amendment cycles

| Cycle | Scope | Outcome |
|-------|--------|---------|
| **T7** (FIND-01–03) | Docs / map / logs / packets T2 + plan | **Substantively closed** in `01f388e6` |
| **Re-audit rev 3** | Same bundle + artifact matrix | **FIND-ARCH-1** opened — `packets/T7.md` not in object graph at `plans/` path |
| **Archive `bb7746aa`** | `plans/` → `archive/` for completed plans | **Partially** fixes FIND-ARCH-1 for filesystem reality; **does not** update audit, plan path citations, or verdict |

**Amendment scope:** Right-sized — no §2 reopen, no architecture creep.

**Passes to close:** Original majors needed **one** T7 execution; **merge-readiness** needed a **second** pass (commit T7 packet **or** don’t claim it in §8). Neither happened before archive; audit frozen at **`fail`**.

**First-pass cleanliness:** Implementation first pass was **genuinely strong** on code; audit was **not** too weak — it caught real process gaps (map baseline, deferred prose, undeclared bundle test). Weakness was **§8 claiming artifacts in `HEAD` without `git show` falsifier** on the executor/orchestrator side.

---

## 4. Adversarial pass calibration

### Rejected alternatives (§5.1)

**Nothing notable** invalidated later — parallel leaves + T5 integrator matched execution. Mega-task or standalone UNKNOWN subtask would have worsened merge/conflict surface; merging T4 into T1 would have polluted config testing.

### Load-bearing assumptions (§5.2)

| # | Assumption | Outcome |
|---|------------|---------|
| 1 | `tomllib` / ≥3.11 | **Held** |
| 2 | Keyword-only `HecklerConfig` | **Held** |
| 3 | UNKNOWN vs score gate | **Held** |
| 4 | Prompts via repo root / editable layout | **Held** (T6 documented) |
| 5 | Pipeline test monkeypatch shape | **Held** (updated to `*a, **kw`) |
| 6 | Map baseline vs post-land HEAD | **Closed by T7** at `026d68d` |

### §5.3 highest re-plan risk (T1 TOML mapping)

**Did not materialize** as the failure axis. Audit and amendments focused on **planning archaeology**, not mapping table rework. §2 mapping table did its job (e.g. `pacing_interval` → `min_output_interval_s`).

### §5.4 hidden couplings

| # | Predicted | Materialized? |
|---|-----------|---------------|
| 1 | Reactor signature + pipeline + tests | **Yes** — resolved in code |
| 2 | Prompt layout + tests + loader | **Yes** — T2/T6 |
| 3 | TOML keys vs `persona.toml` | **Yes** — aligned |
| 4 | `HECKLER_PERSONA` strip | **Suspected → ruled out** |
| 5 | Historical `T7.md` prompt paths | **Yes** — supersession banner |
| 6 | `persona-system-T3.md` deferred prose | **Yes** — **FIND-02** |

**Trouble came from §5.4 process couplings (5–6) and Phase 0.5 map policy**, not from T1 mapping novelty — adversarial pass **paid off** on hidden couplings even when §5.3 risk target was slightly wrong.

---

## 5. Methodology gaps surfaced

### Orchestrator

- **§8 / artifact chain** must require `git ls-files` / `git show HEAD:<path>` for every declared packet and decision log **before** “Complete” — plan listed `T7.md` while commit `01f388e6` omitted it.
- **Path stability after archive:** Moving `plans/` → `archive/` without an audit addendum leaves **`fail`** verdict and stale `.dev/plans/...` citations in the audit file — orchestrator handoff should say “if bundle is archived, pin audit to archive paths or run revision N.”
- **Audit revision discipline:** Replacing rev 1 with rev 3 in one commit **without** retaining rev 2 loses audit DAG for “what failed between passes.” Consider committing each audit revision or appending §“Finding status” only.

### Executor

- **T7:** Delivered map + plan + logs but left **`packets/T7.md`** out of the T7 commit — executor outputs table in packet listed plan paths only, but plan §6 explicitly emitted `T7.md`.
- **T3 / orchestrator staging:** Rev 1 caught `persona-system-T3.md` and plan packets **not in HEAD** at audit time — same class as FIND-ARCH-1, caught earlier as **minor** because code was already landed.

### Auditor skill

- **Worked as designed** on FIND-01–03 and FIND-ARCH-1.
- **Rev 3 HEAD pin `4e8f91f`** vs today’s **`adcbec9b`:** Re-running Phase 0.5 at current HEAD would need archive paths; strict check on `plans/persona-system/packets/T7.md` is **obsolete** if intent is archive bundle — but audit file was never updated → **latent false fail** on paper.

### Contracts schema

**Nothing notable** missing — §2 was the right normative layer; T7 correctly did not edit §2.

### Skill edits

**Do not edit skills in this file.** Patterns worth manual promotion after more retros:

- §8 checklist row: **“Every §6 packet path resolves in `HEAD`.”**
- Post-land context map: **reflexive baseline SHA** (as transcription-engine T6 later codified) — persona T7 did this once; v1.0 intake language caused FIND-01 until explicit §0 rule.

---

## 6. Single sentence verdict

**Partially** — contract-first parallel execution and the audit→**T7** loop **held** for runtime quality and FIND-01–03, but methodology **leaked on git-object closure** (`packets/T7.md` omitted from the T7 commit, §8 over-claimed), **audit lineage** (rev 2 not archived), and **post-archive drift** (bundle moved, audit still `fail` on old `plans/` paths), so process discipline was **strong during the fight** and **incomplete at the archive boundary**.

---

## Appendix — quick reference

| Item | Location |
|------|----------|
| Archived plan | `.dev/archive/persona-system/plan.md` |
| Audit (rev 3, verdict `fail`) | `.dev/audits/2026-05-16-persona-system.md` |
| T7 packet (in `HEAD` at archive path) | `.dev/archive/persona-system/packets/T7.md` |
| Learning twin | `.dev/retrospectives/learning/2026-05-16-persona-system.md` |
| Shorter methodology pass | `.dev/retrospectives/methodology/2026-05-16-persona-system.md` |

**Open process actions (not skill edits):** (1) Audit revision 4 with archive paths **or** note FIND-ARCH-1 closed by `bb7746aa`; (2) optional one-line fix in archived plan §5.4 #1 parenthetical; (3) bump `.dev/archive/persona-system/persona-system.md` status if still “not yet implemented.”
