# Audit — sqlite-local-db-obs-langfuse

**Audit document version:** 2.0  
**Date:** 2026-05-09 (re-run)  
**Plan:** `.dev/plans/sqlite-local-db-obs-langfuse/plan.md` **v1.1.0**  
**Context map:** `.dev/plans/sqlite-local-db-obs-langfuse/context-map.md`  
**Repository at audit:** **`0ea0f4efd2bc903b4706db7d97129fa1e441a859`** (`sqlite`); working tree **clean** (`master...origin/master`).  
**Auditor focus (Phase 4):** **Integration seams** (reactor → `tracing_context` → `HecklerLogger` → `event_store`; pipeline call order), **failure paths** (SQLite insert errors, LLM exceptions, correlation lifecycle), **regression surface** (committed tree vs §2 *Landed*).

---

## 1. Audit metadata

| Field | Value |
|--------|--------|
| **Task name** | sqlite-local-db-obs-langfuse |
| **Plan version** | 1.1.0 |
| **Context map path** | `.dev/plans/sqlite-local-db-obs-langfuse/context-map.md` |
| **Readiness verdict (planning time)** | READY |
| **Provenance check (commits)** | Context map records scout SHA **`0afd022fc5c9b83872a3bc6b015aa6627eed6ee5`**. Audit **`HEAD`** is **`0ea0f4efd2bc903b4706db7d97129fa1e441a859`**. Plan §8 cites post-execution **`b9b24afb09280787e41d42302d4c613d2f81cbd6`** — that commit is an **ancestor** of **`HEAD`** but **does not** contain **`heckler/event_store.py`** (SQLite landed in **`0ea0f4e`**). |
| **File-map drift (map SHA → HEAD)** | Diverged paths: **`heckler/config.py`**, **`heckler/logger.py`**, **`heckler/reactor.py`**, **`tests/test_context_buffer_and_logger.py`**, **`tests/test_models.py`**, **`tests/test_reactor.py`**. Other §File map rows unchanged between **`0afd022`** and **`HEAD`** for the enumerated paths. New modules **`heckler/event_store.py`**, **`heckler/tracing_context.py`**, **`tests/test_event_store.py`**, **`scripts/import_legacy_jsonl.py`** are **plan-predicted additions**, not scout rows. |
| **Working tree at audit** | **Clean** (no dirty-path caveat vs v1.0 audit). |
| **Tests run** | `python -m pytest tests -q` → **113 passed** (against **`HEAD`**). |
| **Phase 0 ordering note** | Cold-read items were pinned from **§1 task statement + §2 contracts + `HEAD` code/tests** before narrative reconciliation; strict isolation of “no plan prose beyond §1–§2” was not a separate filesystem read pass. |

---

## 2. Provenance log (Phase 0.5)

| Check | Result |
|--------|--------|
| **Context map path + verdict** | Present; **READY** (see map header). |
| **SHA comparison (map header vs `HEAD`)** | **Diverged** (`0afd022` ≠ `0ea0f4e`). Expected: scout snapshot predates SQLite implementation. File-map rows that changed are listed in §1 metadata; scout predictions on those paths are **stale-qualified** (implementation intentionally supersedes pre-plan inventory). |
| **Plan §8 SHA vs SQLite tree** | **`b9b24af`** does **not** include **`heckler/event_store.py`**. **`HEAD`** does. Treat plan §8 “tree SHA at plan closure” as **stale for SQLite file presence** unless amended to **`0ea0f4e`** (or later). |
| **Scout working tree (map header)** | **dirty** — `thoughts_so_far.md` only (out of package scope; same as v1). |
| **Audit-time working tree** | **Clean** — no **dirty-state caveat** on implementation files. |
| **Scout grep coverage vs plan §5.4** | Plan §5.4 asks to disprove duplicate instrumentation via grep for **`callback`**, **`langfuse`** outside **`reactor`**. Map §Coupling surfaces bundles `langfuse` in a pattern row but does **not** record an explicit standalone **`callback`** / global LiteLLM hook pattern row. → **`scout-incomplete`** (minor, pre-plan feedback). |

**Phase 0.5 findings filed here**

| ID | Type | Severity | Note |
|----|------|----------|------|
| P1 | `scout-incomplete` | minor | §5.4 duplicate-root disproof vocabulary not fully mirrored in map’s “Grep patterns checked” list (`callback` / global LiteLLM hook patterns). |
| D1 | `process-violation` | minor | Plan §8 **`b9b24af`** anchor predates the commit that introduces **`event_store` / SQLite logger**; use **`0ea0f4e`** (or current **`HEAD`**) for “sqlite landed” provenance (orchestrator handoff doc). |

---

## 3. Context chain completeness

| Artifact | Status |
|----------|--------|
| Context map | **Provided** |
| Pre-plan analysis (`thoughts_so_far.md` etc.) | **Not** used as primary input |
| Orchestrator plan | **Provided** (full `plan.md`) |
| Shared contracts (§2) | **Provided** |
| Decision logs T12–T15 | **Provided** (tracked under `.dev/decision-logs/`) |
| Changelog (`CHANGELOG.MD` sqlite section) | **Provided** |
| Codebase | **`HEAD`** (`0ea0f4e`) |
| Tests | **Provided** + pytest executed |

**Resolved vs v1.0:** **`HEAD`** now contains SQLite-only **`HecklerLogger`**, **`event_store`**, **`tracing_context`**, reactor metadata/correlation, and **`scripts/import_legacy_jsonl.py`**. The v1.0 **F1** git mismatch is **closed**.

---

## 4. Cold-read log (Phase 0)

Pinned from **task statement + §2 contracts + `HEAD` code/tests**:

1. **`heckler/logger.py`:** Inserts via **`serialize_heckle_event`** → **`json.dumps`**, optional **`correlation_json`** from **`tracing_context`**; insert failures log **ERROR** and **re-raise**; **`finally: clear_correlation()`** — matches §2 error envelope and correlation lifecycle.
2. **`heckler/reactor.py`:** **`clear_correlation()`** before **`litellm.completion`**; on API exception, clear and **`LLM_ERROR`** tuple unchanged; on success, primitive-only correlation; **`metadata`** only when hosted observability env active — aligns with §2.
3. **`heckler/event_store.py`:** WAL, busy timeout, **`check_same_thread=False`**, schema version gate — consistent with T12.
4. **`heckler/tracing_context.py`:** **`threading.local`** — within plan allowance (thread-local or contextvar).
5. **`heckler/config.py`:** **`sqlite_database_path`**, **`HECKLER_DATABASE_PATH`** strip / falsy fallback — matches §2.
6. **Integration note:** Correlation set after successful completion persists on the reaction thread until **`log_event`**’s **`finally`**; pipeline should call **`log_event`** on all paths that need persistence — covered by existing tests and worker structure.

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| ~~F1~~ | — | — | — | — | **Resolved (v2.0):** SQLite + tracing are **committed** at **`HEAD`**; v1.0 concern was uncommitted / wrong-tree review. |
| F2 | minor | `decision-log-stale` | 3 | T13 | **T13** “Chosen approach” / deferred items still describe **interim JSONL** under the DB parent and “logger still writes JSONL until T3”; final shipped state is **SQLite-only** — log should be amended for post-T3 truth. |
| P1 | minor | `scout-incomplete` | 0.5 | — | Map grep list missing explicit §5.4 **`callback`** / global-hook disproof patterns (v1.0 **P1**, unchanged). |
| D1 | minor | `process-violation` | 0.5 | — | Plan §8 **`b9b24af`** does **not** contain **`heckler/event_store.py`**; narrated “landed” SQLite tree aligns with **`0ea0f4e`**, not §8 as written (orchestrator / auditor handoff). |
| O1 | observation | — | 4 | — | **`langfuse` / LiteLLM callback** wiring: package code uses env-gated **`metadata`** at **`litellm.completion`** only; no competing global callback registration found in **`heckler/*.py`**. |

---

## 6. Detailed findings (> minor severity)

**None.** Remaining actionable items are **minor** (**D1**, **F2**, **P1**) and are summarized in §5 and §13.

---

## 7. Adversarial test log (Phase 4)

| # | Focus | Scenario | Expected | Actual | Result |
|---|--------|-----------|----------|--------|--------|
| A1 | Integration seam | Successful `litellm.completion` → correlation → `log_event` same thread | Row carries `correlation_json` when set; cleared after insert | `finally: clear_correlation()`; tests `test_logger_writes_correlation_json_when_set`, `test_correlation_set_from_completion_response_ids` | **passes** |
| A2 | Integration seam | `litellm.completion` raises | No correlation leak; `LLM_ERROR` | `clear_correlation()` in `except`; `test_llm_exception_resets_correlation_thread_local` | **passes** |
| A3 | Integration seam | Hosted observability env off | No `metadata` kwarg to LiteLLM | `test_litellm_completion_has_no_metadata_without_observability_env` | **passes** |
| A4 | Integration seam | Env on | `metadata.generation_name == heckler.react` | `test_litellm_completion_gets_metadata_when_hosted_observability_env` | **passes** |
| A5 | Failure path | SQLite insert raises | ERROR log + re-raise + correlation cleared | `test_logger_insert_failure_logs_error_and_raises`, `test_logger_clears_correlation_after_failed_insert` | **passes** |
| A6 | §5.4 coupling | Duplicate LiteLLM roots / global Langfuse callback outside reactor | None for hosted tracing | No `litellm.success_callback` / Langfuse SDK registration in **`heckler/*.py`**; **`reactor`** only sets env-gated **`metadata`** | **passes** (O1) |
| A7 | Regression | `serialize_heckle_event` sole payload authority | DB payload matches model projection | `test_logger_row_payload_equals_models_projection`, `test_logger_payload_matches_serialize_heckle_event` | **passes** |

**Integration seams waiver:** Not applicable.

---

## 8. Coverage gap list (Phase 5)

| Item | Severity | Note |
|------|----------|------|
| **`scripts/import_legacy_jsonl.py`** | minor / accepted deferral | Plan T6 / CHANGELOG: **no dedicated pytest** — matches declared deferral. |
| **`Connection.close()` on shutdown** | observation | T14 deferred; unchanged. |
| **Kill criteria → tests** | — | Concurrent inserts / schema mismatch (`test_event_store.py`), insert failure, metadata/correlation (`test_reactor.py`, logger tests) — covered. |

---

## 9. Phase 1 — Intent traceability (summary)

- **Task ↔ code (`HEAD`):** SQLite-only store, unified serialization, reactor-local LiteLLM **`metadata`** + **`tracing_context`** correlation, optional legacy import script — **met**.
- **Non-goals:** No steady-state dual-write JSONL; no audio in DB; no SQLAlchemy; **`--list-devices`** only (`pipeline.py`); T6 script standalone — **respected**.
- **Map → plan §4:** New modules and script align with plan; scout file map did not pre-list them — **acceptable** with plan §0 intake.
- **§Interface inventory `suspect_modified`:** **`HecklerConfig`**, **`HecklerLogger`**, **`Reactor`** — reflected in §2 and implementation.

---

## 10. Phase 2 — Contract compliance (summary)

| Contract topic | Verdict (`HEAD`) |
|----------------|------------------|
| Types / `sqlite_database_path`, **`HECKLER_DATABASE_PATH`** | **pass** |
| Logger signatures | **pass** |
| Single JSON projection | **pass** |
| SQLite error envelope | **pass** |
| `Reactor.react` / `LLM_ERROR` | **pass** |
| No global LiteLLM callback mutation for observability | **pass** |
| CLI | **pass** (`--list-devices` only) |

---

## 11. Phase 3 — Decision logs (summary)

| Log | vs code (`HEAD`) |
|-----|------------------|
| **T12** | Matches `event_store` + `tracing_context` + WAL/thread model. |
| **T13** | Config/env matches; **F2** prose drift on JSONL. |
| **T14** | Matches logger + `finally` clear + insert failure; `close()` deferred as stated. |
| **T15** | Matches metadata gating + primitive correlation + no global Langfuse callback registration. |

---

## 12. Scout–prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| Surface 1 — `log_dir` ↔ logger/config | confirmed | **verified** — `log_dir` removed; `sqlite_database_path` + env | — |
| Surface 2 — `HeckleEvent` ↔ pipeline ↔ logger | confirmed | **verified** — `serialize_heckle_event` → DB | — |
| Surface 3 — duplicate JSON coercion | confirmed | **verified** — logger uses models projection only (tests enforce) | — |
| Surface 4 — LiteLLM duplicate trace roots | confirmed (owner resolved) | **verified** — single `litellm.completion` surface + `metadata` | O1 |
| Surface 5 — daily JSONL / operators | confirmed | **verified** — SQLite steady state; T6 import script | — |
| §5.4 — tracing + SQLite correlation | suspected | **not-tested** live against Langfuse; code + tests favor single-surface design | — |
| §5.4 — T3 ∥ T4 import drift | suspected | **ruled-out** — imports resolve; pytest green | — |
| Ambiguity — optional JSONL import | residual | **verified** — `scripts/import_legacy_jsonl.py` with documented flags | — |
| `completion_assistant_text` thin coverage | `missing_test_coverage` note | **partially improved** by reactor tests | observation |

---

## 13. Verdict

**`pass-with-conditions`**

**Resolved blocking (vs v1.0):** Implementation matches §2 *Landed* at **`HEAD`**; **113** tests green on the **committed** tree.

**Conditions (non-blocking but should be cleaned up):**

1. **D1** — Amend plan §8 provenance SHA (or prose) so it points at a commit that actually contains **`heckler/event_store.py`** (**`0ea0f4e`** or later).
2. **F2** — Amend **`.dev/decision-logs/T13.md`** to remove interim-JSONL narrative inconsistent with shipped T3.
3. **P1** — Pre-plan-exploration: extend §Coupling surfaces grep inventory for §5.4-style **`callback`** / LiteLLM global-hook patterns on future maps.

---

## 14. Scout feedback (P1)

Add to future context maps’ §Coupling surfaces grep inventory when plans cite §5.4-style disproofs: e.g. **`litellm.success_callback`**, **`success_callback`**, or **`callback`** scoped to LiteLLM usage — distinct from **`CommentType.CALLBACK`** / **`sounddevice`** noise — so scout completeness aligns with orchestrator coupling vocabulary.
