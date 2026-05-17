# Audit — persona-system

**Audit document revision:** 3 — supersedes **revision 2** for **provenance**, **findings**, **verdict**, and **Phase 0.5 artifact checks**. Revision 2 majors **FIND-01** (`context-map-stale`) and **FIND-02** (`decision-log-stale`) are **re-verified resolved** at this HEAD. **FIND-03** (T2 packet vs `test_persona_prompt_bundle.py`) is **resolved**.

**Plan version:** 1.1 (`persona-system` — T7 audit remediation narrative in plan §0 / §7 / §8)  
**Date:** 2026-05-16 (re-audit)  
**Repository HEAD at audit:** `4e8f91f4be6ba8cfac6172e1b34fb82fe8dd4218` (branch `cursor/f1bc42c2`)  
**Context map baseline (Phase 0.5):** `026d68d6dfd3507f7c4debf93a1cf94ad6ea0239` — **ancestor of audit HEAD**; per-row `git diff --quiet 026d68d HEAD -- <path>` for every **§File map** path → **exit 0** (no blob drift on listed runtime + test paths).

**Auditor focus areas (Phase 4):** Integration seams (persona vs transcribe, Reactor signature, TOML mapping) · Failure paths · Env / bundle edge cases.

**Omission-free checklist (re-audit vs revision 2):** Re-read `plan.md` v1.1 §0–§8, `context-map.md` (T7 regen), `packets/T1.md`–`T6.md`, `persona-system-T1.md`, `persona-system-T3.md` (superseded Items deferred), `T7.md` (reactor decision log), `CHANGELOG.MD` persona slice, `heckler/persona.py`, `reactor.py`, `config.py`, `pipeline.py`, `prompts/heckler/*`, `tests/test_persona.py`, `test_persona_prompt_bundle.py`, `test_reactor.py`, `test_pipeline.py`, `test_models.py`; `git show HEAD:` artifact matrix; full `pytest tests/`.

---

## 1. Audit metadata

| Field | Value |
|--------|--------|
| Task name | persona-system (v1.1 closure + T7 doc remediation) |
| Context map | `.dev/plans/persona-system/context-map.md` |
| Readiness at map SHA | **READY** (per map header) |
| Working tree at audit | **Dirty** (local `.dev/` mass-delete + `??` paths); audit evidence uses **`git show HEAD:`** and committed blobs for **Phase 0.5** unless noted. |

---

## 2. Provenance log (Phase 0.5)

- **Context map path / SHA:** `.dev/plans/persona-system/context-map.md` generated against **`026d68d6dfd3507f7c4debf93a1cf94ad6ea0239`** (T7 rescout). Header records **dirty-state caveat** for the scout worktree (changes **outside** the map); no §File map path is listed as dirty-only in the header → **no `dirty-state caveat`** downgrade applied to scout rows on mapped paths.

- **SHA / file divergence (strict):** For each path in the regenerated map **§File map** (rows through `tests/test_persona_prompt_bundle.py`), `git diff --quiet 026d68d6dfd3507f7c4debf93a1cf94ad6ea0239 HEAD -- <path>` → **0** for all. **`context-map-stale`:** **none** (FIND-01 from revision 2 **resolved**).

- **Scout grep vs §5.4:** Map §Coupling surfaces / grep patterns remain aligned with plan §5.4 coupling intent. **No `scout-incomplete`** filed.

- **Plan-declared artifacts (`git show HEAD:<path>`):**

  | Artifact | HEAD |
  |----------|------|
  | `.dev/plans/persona-system/plan.md` | present (v1.1) |
  | `.dev/plans/persona-system/context-map.md` | present |
  | `.dev/plans/persona-system/packets/T1.md`–`T6.md` | present |
  | `.dev/plans/persona-system/packets/T7.md` | **absent** (see **FIND-ARCH-1**) |
  | `.dev/decision-logs/persona-system-T1.md` | present |
  | `.dev/decision-logs/persona-system-T3.md` | present (Items deferred superseded) |

- **Closure:** Plan §8 lists implementation closure `809ba45…` and T7 doc commit `01f388e…`; both are **ancestors** of `4e8f91f` (verified via `git merge-base --is-ancestor`).

---

## 3. Context chain completeness

| Artifact | Status |
|----------|--------|
| Context map (T7 baseline) | Provided |
| Plan v1.1 + §7 amendment / §8 handoff | Provided |
| Packets T1–T6 | Provided at HEAD |
| Packet T7 | **On disk only** (not in HEAD) — **gap** |
| Decision logs T1, T3 | Provided |
| Changelog | Provided |
| Code + tests | Provided |
| Phase 0 ordering | Task statement + §2 read first; narrative (§7 T7 scope) cross-checked in Phase 1. |

---

## 4. Cold-read log (Phase 0 — pinned)

Against §1 / §2 and current `heckler/` + `tests/`:

1. **Persona / reactor / pipeline** match §2 signatures and UNKNOWN fallback string literals.
2. **`_flatten_persona_toml` passthrough** of unmapped keys within known sections remains a **low-risk** coupling (unchanged from revision 2 cold-read); still not a §2 violation.
3. **Transcription-engine fields** on `HecklerConfig` / `--mode transcribe` — **observation** (concurrent plan); persona path remains correctly sequenced after transcribe early-return.
4. **`Reactor._parse_response` docstring** still undersells UNKNOWN fallback (“valid CommentType”) — **observation** (doc drift inside reactor only).

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| FIND-ARCH-1 | major | `artifact-not-in-HEAD` | 0.5 | T7 | Plan §6 / §8 lists `packets/T7.md` as emitted/tracked; `git show HEAD:.dev/plans/persona-system/packets/T7.md` **fails** (file exists untracked on disk only). |
| ~~FIND-01~~ | — | `context-map-stale` | — | — | **resolved** — map regen + per-path `diff --quiet` clean vs `026d68d`→`HEAD` |
| ~~FIND-02~~ | — | `decision-log-stale` | — | T3 | **resolved** — `persona-system-T3.md` Items deferred superseded + Landed section |
| ~~FIND-03~~ | — | `undeclared-change` | — | T2 | **resolved** — T2 packet + context map cite `test_persona_prompt_bundle.py` |

---

## 6. Detailed findings (> minor)

### FIND-ARCH-1 — `artifact-not-in-HEAD` (major)

**Expected:** Plan §6 executor packets and §8 artifact chain include **`T7.md`**. Orchestrator §8 / auditor skill: declared deliverables must exist at **`HEAD`** for merge archaeology.

**Found:** `git show HEAD:.dev/plans/persona-system/packets/T7.md` → *fatal: path … not in 'HEAD'*. Worktree shows **`?? .dev/plans/persona-system/packets/T7.md`** (untracked).

**Remediation:** `git add .dev/plans/persona-system/packets/T7.md` and commit (user rule: commit only when user asks — **flag for user**).

---

## 7. Intent traceability (Phase 1) — summary

- **v1.1 T7 scope** (FIND-01–03) is reflected in **plan §0**, **regenerated context map** (`026d68d`), **T3 log hygiene**, **T2 packet** cross-cutting test note, and **§8** completion narrative.
- **Non-goals** from §1: no prohibited broad edits observed in persona-scoped surfaces.
- **Plan §5.4 hidden coupling #1** evidence parenthetical still cites **`pipeline.py:255` `Reactor(config)`** — **obsolete** vs shipped `Reactor(config, persona.system_prompt, persona.examples)` at ~415 (**observation**; disposition table §5.4 #1 already marks coupling **resolved**).

---

## 8. Contract compliance (Phase 2) — summary

§2 types, logging literals, TOML mapping, CLI `--persona`, error envelope, and tests cited in §2 — **verified** against `heckler/` + tests; unchanged from prior passing audits.

---

## 9. Decision log audit (Phase 3) — summary

- **`persona-system-T1.md`:** Consistent with `persona.py`. **OK**
- **`persona-system-T3.md`:** Items deferred superseded; **Landed** matches `pipeline.py` / `test_pipeline.py`. **OK** (FIND-02 closed)
- **`T7.md` (reactor):** Current behavior + persona supersession consistent with code. **OK**

---

## 10. Adversarial test log (Phase 4)

| Scenario | Expected | Result |
|----------|----------|--------|
| Persona branch composes T1–T4 outputs | `load_persona` → overrides → three-arg `Reactor` | **passes** (`pipeline.py` ~387–415) |
| `PersonaNotFoundError` | message + non-zero exit | **passes** |
| UNKNOWN + score gate | low score still discarded | **passes** (suite) |
| `--list-devices` | short-circuit before persona | **passes** |
| Transcribe mode | no persona load / no `Reactor` | **passes** (suite) |
| §Coupling surfaces (regenerated map) | prior scout surfaces 1–5 | **verified / ruled-out** as in revision 2 reconciliation |

---

## 11. Coverage gap list (Phase 5)

- Ambiguity flags from **v1.0** map: **resolved** in v1.1 narrative + tests.
- Kill criteria for T1–T6: still covered; **no new gaps** identified.
- **FIND-ARCH-1** is process/archaeology — **not** a pytest gap.

**pytest:** `python -m pytest tests/` → **202 passed**, ~9.2s (matches plan §8.1 claim).

---

## 12. Verdict

**`fail`**

**Must resolve before merge (major):**

1. **FIND-ARCH-1** — Add and commit **`.dev/plans/persona-system/packets/T7.md`** so plan §6/§8 artifact chain matches **`HEAD`**.

**Optional polish (non-blocking):**

- Update plan **§5.4** hidden-coupling #1 evidence parenthetical to current line numbers / three-arg `Reactor` call (remove stale `Reactor(config)` cite).

---

## 13. Scout-prediction reconciliation

(Regenerated map at `026d68d`; predictions align with shipped layout. Stale caveat from revision 2 **lifted** for §File map rows — baseline matches `HEAD` blobs on listed paths.)

| Scout prediction | Type | Outcome |
|------------------|------|---------|
| Surfaces 1–4 (JSON type, bundle path, TOML keys, T7 path assumption) | confirmed | **verified** post–T7 map |
| Surface 5 (`HECKLER_PERSONA` strip) | suspected | **ruled out** (tests) |
| Historical ambiguity flags 1–4 | resolved in v1.0 work | **verified** |

---

## 14. Finding status vs revision 2

| Rev 2 ID | Severity | Type | Status | Evidence at HEAD `4e8f91f` |
|----------|----------|------|--------|-----------------------------|
| FIND-01 | major | `context-map-stale` | **resolved** | Map SHA `026d68d`; all §File map paths `diff --quiet` clean vs `HEAD` |
| FIND-02 | major | `decision-log-stale` | **resolved** | `persona-system-T3.md` supersession + Landed |
| FIND-03 | minor | `undeclared-change` | **resolved** | T2 packet + file map row for `test_persona_prompt_bundle.py` |

---

## 15. Auditor closing note

Implementation and **202** tests are **green**. The remaining gate is **purely archival**: **`T7.md` packet not in `HEAD`** despite the plan bundle claiming it is. After that file is committed, a **revision 4** pass should be able to return **`pass`** (assuming a clean artifact matrix).
