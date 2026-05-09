# Audit — sqlite-local-db-obs-langfuse

**Audit document version:** 1.0  
**Date:** 2026-05-09  
**Plan:** `.dev/plans/sqlite-local-db-obs-langfuse/plan.md` **v1.1.0**  
**Context map:** `.dev/plans/sqlite-local-db-obs-langfuse/context-map.md`  
**Auditor focus (Phase 4):** **Integration seams** (reactor → `tracing_context` → `HecklerLogger` → `event_store`; pipeline call order), **failure paths** (SQLite insert errors, LLM exceptions, correlation lifecycle), **regression surface** (committed tree vs narrated “landed” state).

---

## 1. Audit metadata

| Field | Value |
|--------|--------|
| **Task name** | sqlite-local-db-obs-langfuse |
| **Plan version** | 1.1.0 |
| **Context map path** | `.dev/plans/sqlite-local-db-obs-langfuse/context-map.md` |
| **Readiness verdict (planning time)** | READY |
| **Provenance check (commits)** | Context map records scout SHA **`0afd022fc5c9b83872a3bc6b015aa6627eed6ee5`**; plan §8 records post-execution **`b9b24afb09280787e41d42302d4c613d2f81cbd6`**. These differ. For **`heckler/**` paths listed in the context map §File map, `git diff 0afd022..b9b24af -- heckler/` is **empty** — committed package source at HEAD matches scout-time content for those paths. |
| **Working tree at audit** | **Dirty:** modified `heckler/config.py`, `heckler/logger.py`, `heckler/reactor.py`, `tests/*`, `README.md`, `CHANGELOG.MD`, `.env.example`, `.dev/plans/.../plan.md`, `thoughts_so_far.md`; untracked `heckler/event_store.py`, `heckler/tracing_context.py`, `tests/test_event_store.py`, `scripts/`, `.dev/decision-logs/T12.md`–`T15.md`. |
| **Tests run** | `python -m pytest tests -q` → **113 passed** (against **working tree** code, not necessarily `git show HEAD:`). |
| **Phase 0 ordering note** | The full plan and changelog were consulted in one session with code; **cold-read findings were pinned from code + §1–§2 contracts** before Phase 1 narrative reconciliation. Strict “no plan prose beyond §1–§2 before Phase 0” was not isolated as a separate read pass. |

---

## 2. Provenance log (Phase 0.5)

| Check | Result |
|--------|--------|
| **Context map path + verdict** | Present; **READY** (see map header). |
| **SHA comparison (map vs HEAD)** | **Diverged commits** (`0afd022` ≠ `b9b24af`). **File-level:** between those two SHAs, **no** changes under `heckler/` per `git diff --name-only 0afd022 b9b24af -- heckler/`. Staleness of *scout predictions against the map’s own snapshot* for `heckler/*.py` is therefore **not** triggered by commit-to-commit drift on those paths. |
| **Working tree vs HEAD** | **Large drift:** SQLite implementation, new modules, tests, scripts, and decision logs exist in the **working tree** but **`git ls-tree HEAD heckler/`** does **not** list `event_store.py` or `tracing_context.py`; **`git show HEAD:heckler/logger.py`** still shows JSONL + `_coerce_json`. |
| **Scout working tree (map header)** | **dirty** — `thoughts_so_far.md` only (in-scope for “not runtime” caveat). |
| **Audit-time dirty paths** | Broader than scout: all implementation and doc paths above. **Dirty-state caveat** applies to any finding that assumes these paths are identical to a clean commit. |
| **Scout grep coverage vs plan §5.4** | Plan §5.4 asks to disprove duplicate instrumentation via grep for **`callback`**, **`langfuse`** outside `reactor`. Map §Coupling surfaces lists `langfuse` in a bundle pattern but does **not** record a dedicated **`callback`** / **`litellm.success_callback`** (or similar) pattern row. → **`scout-incomplete`** (minor, process feedback to pre-plan-exploration). |

**Phase 0.5 findings filed here**

| ID | Type | Severity | Note |
|----|------|----------|------|
| P1 | `scout-incomplete` | minor | §5.4 duplicate-root disproof vocabulary not fully mirrored in map’s “Grep patterns checked” list (`callback` / global LiteLLM hook patterns). |

---

## 3. Context chain completeness

| Artifact | Status |
|----------|--------|
| Context map | **Provided** |
| Pre-plan analysis (`thoughts_so_far.md` etc.) | **Not** used as primary input |
| Orchestrator plan | **Provided** (full `plan.md`) |
| Shared contracts (§2) | **Provided** |
| Decision logs T12–T15 | **Provided** (in working tree; **untracked** in git) |
| Changelog (`CHANGELOG.MD` sqlite section) | **Provided** |
| Codebase | **Working tree** read for implementation; **HEAD commit** spot-checked for closure SHA honesty |
| Tests | **Provided** + pytest executed |

**Limitation:** Auditing “merge readiness” against **`b9b24afb09280787e41d42302d4c613d2f81cbd6`** as the **sole** source of truth would **fail** — that commit does not contain the SQLite migration. Evidence below under **F1**.

---

## 4. Cold-read log (Phase 0)

Pinned from **task statement + §2 contracts + working-tree code/tests** (minimal narrative priming):

1. **`heckler/logger.py` (working tree):** Single insert path using `json.dumps(serialize_heckle_event(...))` + optional `correlation_json`; errors logged at ERROR and re-raised; `finally` clears correlation — matches §2 error envelope and correlation lifecycle intent.
2. **`heckler/reactor.py`:** `clear_correlation()` before completion; on API exception, clear and return `LLM_ERROR`; on success, derive flat string correlation from response primitives only; optional `metadata` only when env gates pass — aligns with §2 “no duplicate global callbacks” direction.
3. **`heckler/event_store.py`:** WAL + `check_same_thread=False` + connect `timeout=30`; `init_schema` version gate — consistent with T12 narrative.
4. **`tracing_context.py`:** `threading.local` — matches plan; **not** `contextvars` (plan allowed either).
5. **Risk (integration):** `Reactor.react` leaves correlation set on the worker thread after a **successful HTTP response** until `HecklerLogger.log_event` runs; the pipeline’s reaction worker always calls `log_event` on discard/success paths in the happy path, and the next `react()` clears at entry — **acceptable** if `log_event` is never skipped between them (see Phase 4). Worker-wide `except Exception` without `log_event` could skip logging but next `react` still clears — **low** orphan-correlation risk.
6. **Git vs tree mismatch (cold):** New package files and logger rewrite are **not** in `git ls-tree HEAD heckler/` — **merge / release blocker** if maintainers believe §8 closure SHA is the shipped tree.

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| F1 | **critical** | `process-violation` / narrative–git mismatch | 0.5 / 1 | T1–T5 | Plan §8 and CHANGELOG describe SQLite + tracing as **landed** at **`b9b24afb09280787e41d42302d4c613d2f81cbd6`**, but **that commit’s** `heckler/` tree is still **JSONL** `HecklerLogger` (no `event_store` / `tracing_context`). Implementation reviewed here is **uncommitted** (modified + untracked). |
| F2 | minor | `decision-log-stale` | 3 | T13 | T13 “Chosen approach” still says **`HecklerLogger`** keeps **interim JSONL** under the DB parent through T2/T3 boundary language; **final** state is SQLite-only per T14/T3 — log not amended for “after T3” truth. |
| P1 | minor | `scout-incomplete` | 0.5 | — | Map grep list missing explicit §5.4 **`callback`** / global-hook disproof patterns. |
| O1 | observation | — | 4 | — | `grep` for `langfuse` / `callback` in `heckler/*.py`: only **`reactor.py`** mentions Langfuse env + LiteLLM metadata; `audio_capture` / `models` use “callback” unrelated to LiteLLM — **§5.4 suspected duplicate-root coupling** not evidenced in package code. |

---

## 6. Detailed findings (> minor)

### F1 — Closure SHA vs git tree (critical)

**Expected:** Repository at plan §8 **post-execution tree SHA** contains the SQLite-only logger, new store module, tracing module, and reactor instrumentation described in §2 *Landed* and `CHANGELOG.MD` **sqlite-local-db-obs-langfuse**.

**Found:** `git ls-tree --name-only HEAD heckler/` has no `event_store.py` / `tracing_context.py`. `git show HEAD:heckler/logger.py` begins with JSONL + `_coerce_json` / `_path_for_date` pattern. Working tree replaces this with SQLite.

**Evidence:** local commands: `git ls-tree HEAD heckler/`, `git show HEAD:heckler/logger.py` (first lines JSONL-era), `git status -sb` (modified + untracked implementation files).

**Action:** Commit (or amend) so **`HEAD`** matches the narrated **landed** state; then re-tag §8 SHA or amend plan §8 to the commit that actually contains the migration.

---

## 7. Adversarial test log (Phase 4)

| # | Focus | Scenario | Expected | Actual | Result |
|---|--------|-----------|----------|--------|--------|
| A1 | Integration seam | Successful `litellm.completion` → correlation set → `log_event` on same reaction thread | Row carries `correlation_json` when metadata present; cleared after insert | `logger.log_event` `finally: clear_correlation()`; tests `test_logger_writes_correlation_json_when_set`, `test_correlation_set_from_completion_response_ids` | **passes** |
| A2 | Integration seam | `litellm.completion` raises | No correlation leak; `LLM_ERROR` tuple | `clear_correlation()` in `except`; `test_llm_exception_resets_correlation_thread_local` | **passes** |
| A3 | Integration seam | Hosted observability env off | No `metadata` kwarg to LiteLLM | `test_litellm_completion_has_no_metadata_without_observability_env` | **passes** |
| A4 | Integration seam | Env on | `metadata.generation_name == heckler.react` | `test_litellm_completion_gets_metadata_when_hosted_observability_env` | **passes** |
| A5 | Failure path | SQLite insert raises | ERROR log + re-raise + correlation cleared | `test_logger_insert_failure_logs_error_and_raises`, `test_logger_clears_correlation_after_failed_insert` | **passes** |
| A6 | §5.4 coupling | Duplicate LiteLLM roots / global `langfuse` callback registration outside reactor | None outside reactor for Langfuse integration | Grep: no `litellm.success_callback` / `langfuse` package imports outside `reactor.py` | **passes** (observation O1) |
| A7 | Regression | `serialize_heckle_event` is sole payload authority | DB payload matches model projection | `test_logger_row_payload_equals_models_projection`, `test_logger_payload_matches_serialize_heckle_event` | **passes** |

**Integration seams waiver:** Not applicable — multiple subsystems meet.

---

## 8. Coverage gap list (Phase 5)

| Item | Severity | Note |
|------|----------|------|
| **`scripts/import_legacy_jsonl.py`** | minor / accepted deferral | Plan T6 / CHANGELOG: **no dedicated pytest**; script docstring checklist + JSON1 doc — **matches declared deferral**. |
| **`Connection.close()` on shutdown** | observation | T14 deferred; no new leak proof in audit — **documented deferral**. |
| **Kill criteria → tests** | — | T1 concurrent inserts + schema mismatch covered in `tests/test_event_store.py`; T3 insert failure covered; T4 metadata/correlation covered in `tests/test_reactor.py`. |

No **major** `coverage-gap` identified beyond the **F1** git-boundary issue (tests green on WD, not on documented closure commit).

---

## 9. Phase 1 — Intent traceability (summary)

- **Task statement ↔ code (WD):** Replace JSONL with SQLite-only store, unify serialization, reactor-local LiteLLM metadata + correlation, optional legacy import — **met** in working tree.
- **Non-goals:** No dual-write steady state; no audio in DB; no SQLAlchemy; CLI remains `--list-devices` only (verified `pipeline.py`); T6 script is standalone — **respected** in working tree.
- **Map → plan §4:** New files (`event_store`, `tracing_context`, `test_event_store`, `scripts/import_legacy_jsonl.py`) align with plan packets; scout file map did not pre-list new modules — **acceptable** with plan §0 intake.
- **§Interface inventory `suspect_modified`:** `HecklerConfig`, `HecklerLogger`, `Reactor` — addressed in §2 and code.

**Narrative-concealment:** None beyond **F1** (changelog/plan closure vs git).

---

## 10. Phase 2 — Contract compliance (summary)

| Contract topic | Verdict (working tree) |
|----------------|-------------------------|
| Types / `HecklerConfig.sqlite_database_path`, env strip | **pass** (`load_config`, tests) |
| Logger signatures | **pass** |
| Single JSON projection | **pass** |
| SQLite error envelope | **pass** |
| `Reactor.react` / `LLM_ERROR` | **pass** |
| No global LiteLLM callback mutation | **pass** |
| CLI | **pass** |

---

## 11. Phase 3 — Decision logs (summary)

| Log | vs code |
|-----|---------|
| **T12** | Matches `event_store` + `tracing_context` + WAL/thread model. |
| **T13** | Matches config/env; **F2** wording drift on interim JSONL. |
| **T14** | Matches logger + `finally` clear + insert failure behavior; `close()` deferred as stated. |
| **T15** | Matches metadata gating + primitive correlation + rejection of global Langfuse callback registration. |

---

## 12. Scout–prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| Surface 1 — `log_dir` ↔ logger/config | suspected_coupling (confirmed in map) | **verified** addressed: `log_dir` removed; `sqlite_database_path` + env — | — |
| Surface 2 — `HeckleEvent` ↔ pipeline ↔ logger schema | confirmed | **verified** — single `serialize_heckle_event` path to DB | — |
| Surface 3 — duplicate JSON coercion logger vs models | confirmed | **verified** — logger duplicate path removed (tests enforce) | — |
| Surface 4 — LiteLLM duplicate trace roots | confirmed (resolved by owner) | **verified** — instrumentation only at `litellm.completion` + metadata; grep shows no competing registration | O1 |
| Surface 5 — daily JSONL pattern / operators | confirmed | **verified** — steady state SQLite; T6 optional import script | — |
| §5.4 — `litellm` tracing + SQLite correlation orphan/duplicate spans | suspected | **not-tested** against live Langfuse; **code + tests** support single-surface design | — |
| §5.4 — T3 parallel T4 import/API drift | suspected | **ruled-out** in current tree (imports resolve; pytest green) | — |
| Ambiguity — optional JSONL import | residual | **verified** — `scripts/import_legacy_jsonl.py` present with documented flags | — |
| `completion_assistant_text` thin tests | missing_test_coverage note | **partially improved** by reactor test suite (not exhaustively branch-tested) | observation |

---

## 13. Verdict

**`fail`**

**Blocking:** **F1** — The documented post-execution SHA **`b9b24afb09280787e41d42302d4c613d2f81cbd6`** does **not** contain the SQLite migration; the reviewed implementation and **113** passing tests apply to the **dirty working tree**, not that commit. Until the migration is **committed** (and §8 / changelog anchors updated to match), the repository is **not** merge- or release-audited as stated.

**Non-blocking:** amend **T13** prose (**F2**); pre-plan-exploration grep vocabulary (**P1**).

---

## 14. Scout feedback (P1)

Add to future context maps’ §Coupling surfaces grep inventory, when plans cite §5.4-style disproofs: e.g. **`litellm.success_callback`**, **`success_callback`**, or **`callback`** scoped to LiteLLM imports — distinct from `sounddevice` / `CommentType.CALLBACK` noise — so scout completeness aligns with orchestrator coupling vocabulary.
