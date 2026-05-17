# Audit — persona-system

**Plan version:** 1.0  
**Date:** 2026-05-16  
**Auditor focus areas:** Integration seams, Edge cases  
**Context map path:** `.dev/plans/persona-system/context-map.md`  
**Readiness verdict at planning time:** CONDITIONAL  
**Provenance check:** SHA diverged (map: `7b5382e`, HEAD: `809ba45`). Only `.dev/` files changed between map SHA and code-landing SHAs; source surfaces not stale. Code-landing SHAs (`d5922a2`..`809ba45`) post-date both. Map is valid for audit purposes.

---

## §Provenance log

- **Context map path:** `.dev/plans/persona-system/context-map.md`
- **SHA comparison:** diverged — map generated at `7b5382e`, HEAD at `809ba45`. Diff `7b5382e..d65c7bf` (planning SHA) touched only `.dev/` files. All source-code changes in the persona-system commits (`d5922a2`..`809ba45`) post-date map generation. **No source files inventoried by the map were modified between map creation and planning.** Map is not stale for inventoried code surfaces.
- **Working-tree state at scout time:** dirty (untracked: `.dev/persona-system.md`, `.dev/transcription-engine.md`). Both are design docs, neither is in §File map scope. No `dirty-state caveat` applies.
- **Scout grep coverage gaps:** None identified. §5.4 contract surfaces all traceable to grep patterns in §Coupling surfaces.
- **Plan-artifact provenance:**

| Artifact | Status |
|----------|--------|
| `.dev/plans/persona-system/plan.md` | on-disk-only (staged, not yet in HEAD) |
| `.dev/plans/persona-system/context-map.md` | present-in-HEAD |
| `.dev/plans/persona-system/packets/T1.md` | on-disk-only (staged) |
| `.dev/plans/persona-system/packets/T2.md` | on-disk-only (staged) |
| `.dev/plans/persona-system/packets/T3.md` | on-disk-only (staged) |
| `.dev/plans/persona-system/packets/T4.md` | on-disk-only (staged) |
| `.dev/plans/persona-system/packets/T5.md` | on-disk-only (staged) |
| `.dev/plans/persona-system/packets/T6.md` | on-disk-only (staged) |
| `.dev/decision-logs/persona-system-T1.md` | present-in-HEAD |
| `.dev/decision-logs/persona-system-T3.md` | on-disk-only (staged) |

- **Findings filed:**
  - F1: `artifact-not-in-HEAD` — `.dev/decision-logs/persona-system-T3.md` not committed by T3 executor. Staged now; will resolve on next commit. **minor** (no code impact; process gap).
  - F2: `artifact-not-in-HEAD` — Plan + packets created in worktree, not committed. Staged now. **minor** (executors received content; archival gap only).

---

## Context chain completeness

| Artifact | Provided |
|----------|----------|
| Context map | ✅ |
| Pre-plan analysis (`.dev/persona-system.md`) | ✅ |
| Orchestrator plan | ✅ |
| Shared contracts (§2) | ✅ |
| Decision logs (T1, T3) | ✅ |
| Codebase | ✅ |
| Test suite | ✅ |

Phase 0 completed before any narrative artifacts were read.

---

## Cold-read log (Phase 0)

Reading only §1, §2, and the codebase diff:

1. **`HecklerConfig` has undeclared fields.** `mode`, `transcribe_max_speech_duration_s`, `transcribe_silence_duration_ms`, `transcribe_min_speech_duration_ms`, `transcripts_dir`, `session_name` — not in plan §2. Likely from concurrent transcription-engine plan. **observation** — does not affect persona contracts.

2. **Pipeline `main()` has `--mode` flag and transcribe branch.** Not in plan §2 CLI surface. Same source: transcription-engine. **observation** — persona wiring correctly guarded behind `mode != "transcribe"` (persona loads only in persona mode path).

3. **`Reactor` constructor signature correct.** `__init__(self, config, system_prompt, examples)` — matches §2.

4. **UNKNOWN fallback correct.** Lines 290–298: `except ValueError` → `ct = CommentType.UNKNOWN` with correct WARNING format string.

5. **Persona module well-structured.** `_TOML_TO_CONFIG` mapping matches §2 table. `_flatten_persona_toml` correctly skips `comment_types`.

6. **T7 decision log supersession banner present.** First line is the supersession notice pointing to `persona-system-T3.md`.

7. **All Reactor tests use new 3-arg constructor.** `_TEST_SYSTEM_PROMPT` and `_TEST_EXAMPLES` constants defined; no remaining 1-arg calls.

8. **Pipeline test monkeypatches updated.** `lambda *a, **kw: MagicMock()` for Reactor; `load_persona` and `apply_persona_overrides` patched. `Persona` imported and constructed as fake fixture.

---

## Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| F1 | minor | `artifact-not-in-HEAD` | 0.5 | T3 | Decision log `persona-system-T3.md` not committed |
| F2 | minor | `artifact-not-in-HEAD` | 0.5 | orchestrator | Plan + packets not committed |
| F3 | observation | `undeclared-change` | 0 | — | `HecklerConfig` has extra fields from transcription-engine plan |
| F4 | observation | `undeclared-change` | 0 | — | Pipeline has `--mode` flag from transcription-engine plan |

---

## Detailed findings

### F1 — `persona-system-T3.md` not committed (minor)

**Expected:** T3 spec declares `.dev/decision-logs/persona-system-T3.md` as an output. Plan §2 declares the path. Should be at HEAD.  
**Found:** File exists on disk but is untracked (`git ls-files` does not list it; `git status` shows `??`).  
**Evidence:** `git ls-files .dev/decision-logs/persona-system*` returns only `persona-system-T1.md`.  
**Resolution:** Staged for commit. Will be in HEAD after next commit.

### F2 — Plan + packets not committed (minor)

**Expected:** `.dev/plans/persona-system/` with `plan.md` and `packets/T1-T6.md` should be tracked.  
**Found:** Untracked; created in worktree during planning, executors ran in main repo.  
**Resolution:** Staged for commit.

---

## Adversarial test log

### Focus 1: Integration seams

**Rationale:** The core risk in this plan is the 4-way parallel merge at T5 — persona module (T1), prompt files (T2), reactor signature (T3), and config field (T4) all have to compose correctly in pipeline.

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| `pipeline.main` loads persona, applies overrides, passes to Reactor | `load_persona` → `apply_persona_overrides` → `Reactor(config, system_prompt, examples)` | Lines 387–415: `persona_name = args.persona or config.persona_name` → `load_persona(prompts_root / persona_name)` → `apply_persona_overrides(config, persona)` → `Reactor(config, persona.system_prompt, persona.examples)` | **passes** |
| `PersonaNotFoundError` caught with user message + exit(1) | Print `[HECKLER] Error:` + SystemExit(1) | Lines 391–393: `except PersonaNotFoundError as exc: print(...) raise SystemExit(1) from exc` | **passes** |
| `--persona` flag overrides `config.persona_name` | CLI value used when provided, else config value | Line 387: `args.persona or config.persona_name` | **passes** |
| TOML mapping: `pacing_interval` → `min_output_interval_s` | Persona with `pacing_interval = 5.5` produces config with `min_output_interval_s == 5.5` | `test_apply_persona_overrides_each_mapping_table_field` asserts exactly this | **passes** |
| Unknown TOML key logged and ignored | WARNING log, field not applied | `test_apply_persona_overrides_warns_on_unknown_keys` + `test_load_persona_passthrough_unknown_key_in_section` | **passes** |
| UNKNOWN type fallback still subject to score gate | Low-score UNKNOWN → `SCORE_GATE` discard | `test_react_unrecognized_type_string_still_hits_score_gate` | **passes** |
| `--list-devices` short-circuits before persona load | No `load_config`, no persona | `test_list_devices_short_circuits` | **passes** |
| Transcribe mode does NOT load persona | No `load_persona` call | `test_main_transcribe_mode_does_not_load_speaker_or_reactor` asserts `load_persona` raises if called | **passes** |

### Focus 2: Edge cases

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Empty `HECKLER_PERSONA` env var | Falls back to `"heckler"` | `test_load_config_persona_name_empty_string_falls_back_to_default` | **passes** |
| Whitespace-only `HECKLER_PERSONA` | Falls back to `"heckler"` | `test_load_config_persona_name_whitespace_falls_back_to_default` | **passes** |
| Persona dir missing | `PersonaNotFoundError("does not exist")` | `test_load_persona_missing_directory_raises` | **passes** |
| `persona.toml` missing from dir | `PersonaNotFoundError("Missing persona.toml")` | `test_load_persona_missing_persona_toml_raises` | **passes** |
| `system.md` missing from persona dir | `PersonaNotFoundError("system.md")` | `test_load_persona_missing_system_md_raises` | **passes** |
| `examples.json` absent (optional) | Empty list | `test_load_persona_without_examples_json` | **passes** |
| `examples.json` is not array | `ValueError("JSON array")` | `test_load_persona_examples_not_array_raises` | **passes** |
| Invalid TOML | `tomllib.TOMLDecodeError` | `test_load_persona_invalid_toml_raises` | **passes** |
| No `[persona]` table | `ValueError("[persona]")` | `test_load_persona_missing_persona_section_raises` | **passes** |
| `list_personas` on missing root | Empty list | `test_list_personas_missing_root_returns_empty` | **passes** |
| Empty overrides (no TOML sections) | Returns copy equal to base | `test_apply_persona_overrides_empty_overrides_returns_copy` | **passes** |

---

## Coverage gap list

No coverage gaps identified. All kill criteria are covered by tests:

- T1 KC1 (tomllib): covered by `test_load_persona_happy_path` using `tomllib` at import
- T1 KC2 (dataclasses.replace): covered by `test_apply_persona_overrides_each_mapping_table_field`
- T3 KC1 (UNKNOWN fallback): covered by `test_invalid_comment_type_in_json_returns_unknown` + two react-level tests
- T3 KC2 (test rename): test renamed successfully
- T4 KC1 (positional args): no positional constructions found; tests pass
- T5 KC1 (Reactor signature): `test_main_passes_persona_prompts_to_reactor`
- T5 KC2 (load_persona importable): all pipeline tests import and mock it
- T5 KC3 (persona_name field): `test_main_persona_flag_overrides_config`
- T6 KC1 (examples.json exists): `test_examples_json_types_are_comment_type_members` reads it successfully
- T6 KC2 (test still present): test exists and passes

---

## Verdict

**`pass-with-conditions`**

**Conditions:**
1. Commit the staged artifacts (plan, packets, T3 decision log) so all plan-declared artifacts resolve at HEAD. This is a documentation/archival condition, not a code condition.

All §2 contracts are satisfied. All 83 tests pass. No critical or major code findings. The two minor findings (F1, F2) are process gaps already resolved by staging — a single commit closes them.

---

## Scout-prediction reconciliation

| Scout prediction | Type | Description | Outcome | Finding ID |
|-----------------|------|-------------|---------|------------|
| Surface 1 (CommentType UNKNOWN) | confirmed coupling | JSON "type" strings and `_parse_response` behavior | verified — UNKNOWN fallback implemented + tested | — |
| Surface 2 (prompt path in test) | confirmed coupling | `test_examples_json_types` uses `prompts/examples.json` path | verified — path updated to `prompts/heckler/examples.json` | — |
| Surface 3 (TOML keys vs config fields) | confirmed coupling | `pacing_interval` vs `min_output_interval_s` | verified — `_TOML_TO_CONFIG` mapping table matches §2 | — |
| Surface 4 (prompt path T7 assumption) | confirmed coupling | T7 assumes `prompts/` at root | verified — supersession banner added to T7.md | — |
| Surface 5 (HECKLER_PERSONA strip) | suspected coupling | Inconsistent strip/empty handling | ruled-out — mirrors HECKLER_LLM_MODEL pattern; tested | — |
| Flag 1 (UNKNOWN vs None) | ambiguity | `_parse_response` behavior fork | verified — resolved as UNKNOWN fallback per design | — |
| Flag 2 (mapping ownership) | ambiguity | Where TOML→config mapping lives | verified — lives in `persona.py` as `_TOML_TO_CONFIG` | — |
| Flag 3 (test coverage) | missing_test_coverage | HECKLER_PERSONA and persona loader untested | verified — 5 config tests + 18 persona tests added | — |
| Flag 4 (coexisting prompts) | ambiguity | Root vs `prompts/heckler/` coexistence | verified — hard cut; old files removed | — |
