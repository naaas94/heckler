# Audit report — sqlite-event-decomposition-analytics

## 1. Audit metadata

| Field | Value |
|--------|--------|
| **Task name** | sqlite-event-decomposition-analytics (SQLite event decomposition for SQL analytics) |
| **Plan** | `.dev/plans/sqlite-event-decomposition-analytics/plan.md` (orchestrator skill **0.6**, plan status **Complete**) |
| **Audit date** | 2026-05-11 |
| **Repository HEAD at audit** | `91687be20a4d2ec707561721bc1777e7eeda39a5` (docs-only delta after application SHA below) |
| **Application / test baseline (plan §8.1)** | `adc6b2c73e10e71d99dbbcf88c1fbf965b166d4c` |
| **Context map path** | `.dev/plans/sqlite-event-decomposition-analytics/context-map.md` |
| **Readiness verdict (scout time)** | **CONDITIONAL** |
| **Phase 0 discipline** | Task statement + plan **§2 Shared contracts** were taken as allowed inputs; **§8.5 cold-read seeds** and application files were read before broader plan §1/§3–§7 narrative. An initial buffered read of plan lines 1–120 occurred in the tooling pass — cold-read list below is pinned from code + §2 + seeds, not from downstream narrative justification. |
| **Phase 4 focus** | **Integration seams** (logger ↔ `insert_heckle_event_row`, import batch ↔ mirrored SQL, migration `BEGIN IMMEDIATE`); **Failure paths** (rollback on child insert / migration); **Regression surface** (legacy `insert_event_row`, schema version gate). |
| **Re-audit** | No — first audit (no prior revision). |

**Auditor note on verdict vs. product risk:** One **major** process finding (`context-map-stale`) is recorded per auditor skill defaults. Application behavior at `adc6b2c` matches plan §2 *Landed* bullets; **pytest** at current workspace: **132 passed** (2026-05-11 run). Merge readiness for *code* is strong; the major finding concerns **scout provenance vs. HEAD**, which the plan partially anticipated in **§0**.

---

## 2. Provenance log (Phase 0.5)

### 2.1 Context map header

| Check | Result |
|--------|--------|
| **Scout commit SHA** | `7d5b1f0b5eb97088b4d4826e868a79dee1bdd4c8` |
| **Audit-time HEAD** | `91687be20a4d2ec707561721bc1777e7eeda39a5` |
| **SHA comparison** | **Diverged** — expected; plan §0 records application baseline `adc6b2c…` and notes map line-level staleness. |
| **Scout working tree** | **dirty** — paths listed in map header: `?? .dev/retrospectives/learning/2026-05-10-sqlite-local-db-obs-langfuse.md`, `?? .dev/retrospectives/methodology/2026-05-10-sqlite-local-db-obs-langfuse.md` — **out of §File map scope** (not under `heckler/`, `tests/`, `scripts/`, `pyproject.toml` rows). No `dirty-state caveat` applied to in-scope code rows. |

### 2.2 Files in §File map with content drift since scout SHA

`git diff --name-only 7d5b1f0… HEAD` for in-scope application roots includes at least:

`heckler/event_store.py`, `heckler/logger.py`, `heckler/pipeline.py`, `scripts/import_legacy_jsonl.py`, `tests/test_event_store.py`, `tests/test_context_buffer_and_logger.py`, `tests/test_import_legacy_jsonl.py`, plus plan/decision-log/packet paths under `.dev/`.

→ **`context-map-stale`** filed (see findings table). Findings that lean on scout-only predictions on those paths are tagged **stale-qualified** where relevant.

### 2.3 Scout grep coverage vs. plan §5.4 contract surfaces

Context map **§Coupling surfaces → Grep patterns checked** lists: `payload_json`, `correlation_json`, `heckler_schema_version`, `insert_event_row`, `SCHEMA_VERSION`, serializers, env/keys, `json_extract`, `HeckleEvent`, `log_event`, `--list-devices`, `.dev/decision-logs/`.

Post-implementation **§5.4** confirmed coupling explicitly references **`insert_heckle_event_row`** transaction / import mirroring. That symbol is **not** in the scout’s grep list → **`scout-incomplete`** (minor), feedback to pre-plan-exploration.

### 2.4 Plan-artifact `git show HEAD:<path>` (§8.2 chain)

All of the following returned content at **HEAD** (`91687be`):

- `.dev/plans/sqlite-event-decomposition-analytics/context-map.md`
- `.dev/plans/sqlite-event-decomposition-analytics/plan.md`
- `.dev/decision-logs/T20-event-decomposition-arch.md`
- `.dev/decision-logs/T21-event-decomposition-schema.md`
- `.dev/plans/sqlite-event-decomposition-analytics/packets/T1.md` … `T5.md`

→ No **`artifact-not-in-HEAD`** or **`artifact-missing`** for the §8.2 list.

**Closure / plan-only SHA:** Plan §8.1 pins application code to `adc6b2c…`; tip `91687be` is a **doc-only** follow-up per `git log`. `git diff adc6b2c HEAD -- heckler tests scripts` is empty — consistent with §8.1 handoff rules.

---

## 3. Context chain completeness

| Artifact | Status |
|----------|--------|
| Context map | **Present** |
| Orchestrator plan | **Present** (full read after Phase 0 pin) |
| Shared contracts (§2) | **Present** |
| Decision logs T20, T21 | **Present** |
| Packets T1–T5 | **Present** |
| Changelog | **Present** — `CHANGELOG.MD` (see observation on casing) |
| Code / tests | **Reviewed** at HEAD for `.dev/`; application behavior pinned to `adc6b2c` per plan |
| Pre-plan analysis / roadmap (outside repo map) | **Not separately supplied** — intent inferred from plan §1 + T20 |

**Limits:** No standalone pre-plan narrative beyond the context map and T20/T21; sufficient because the plan is marked Complete with §8 handoff.

---

## 4. Cold-read log (Phase 0 — pinned)

Issues and risks observed from **§2**, **§8.5 seeds**, and **code** (`adc6b2c` tree for `heckler/`, `tests/`, `scripts/`) without relying on plan §8.4 disposition text:

1. **`insert_heckle_event_row` owns `commit`/`rollback`** while `import_lines` owns a **batch** transaction around `_insert_imported_event` — correct split, but **SQL shape duplication** between import and store is a long-term drift vector (needs tests to stay coupled).
2. **`heckler/event_store.py` module docstring** still suggests normalized columns may not be populated on the live path (“once populated” / legacy wording) even though **T3** populates them — documentation slightly behind implementation (**severity guess:** minor).
3. **Scout §Prior reasoning** row for **T14** still says `log_event` → `insert_event_row` — contradicts shipped code (**stale-qualified**; do not treat as current truth).
4. **Context map §Interface inventory** for `import_lines` still shows **`test_file: none_found`** — falsified by `tests/test_import_legacy_jsonl.py` (**stale-qualified**).

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| F-001 | **major** | `context-map-stale` | 0.5 | — | Scout SHA `7d5b1f0…` ≠ audit HEAD; all touched in-scope files diverged — archive/traceability gap per skill (plan §0 pre-acknowledges line-level staleness). |
| F-002 | minor | `scout-incomplete` | 0.5 | — | §Coupling grep list omits `insert_heckle_event_row` while plan §5.4 tuples depend on it. |
| F-003 | minor | `coverage-gap` | 5 | T4 / §8.3 | No subprocess / argv test for `import_legacy_jsonl.py` CLI — plan §8.3 already flags; tests cover `import_lines` API. |
| F-004 | minor | `coverage-gap` | 5 | T2 / §8.3 | No dedicated assertion that `heckler_eval_labels` exists after `init_schema` — plan §8.3 “Gap” note; DDL implied by `_ensure_auxiliary_tables`. |
| F-005 | observation | — | 1 | T5 | `CHANGELOG.MD` updated but not listed in T5 packet “Files to touch” — benign release hygiene. |
| F-006 | observation | — | 3 | T2 | T21 **“Items deferred”** body still enumerates T3–T5 work; **supersession banner** at top is the operative reader contract — acceptable if readers start at banner. |

---

## 6. Detailed findings (above minor)

### F-001 — `context-map-stale` (major)

**Expected:** For audit archive integrity, context map provenance commit should match the commit tree under review, or the orchestrator should supply a refreshed map at the application SHA.

**Found:** Map frozen at `7d5b1f0…`; audit HEAD `91687be…`; application work landed in `dc06927` … `adc6b2c` with extensive edits to every `direct` file in the map’s §File map.

**Evidence:** Context map lines 3–4; `git diff --name-only 7d5b1f0… HEAD -- heckler tests scripts`; plan §0 “Current repo HEAD / staleness” row.

**Note:** Plan §0 explicitly documents staleness and redirects auditors to §8.5 seeds and T21 supersession — this mitigates *executor confusion* but does not remove the skill’s **`context-map-stale`** classification.

---

## 7. Adversarial test log (Phase 4)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| **Seam:** `HecklerLogger.log_event` + transaction | Single transaction for parent + optional reactor child; lock held for insert window | `log_event` holds `_lock` and calls `insert_heckle_event_row`, which uses one cursor transaction then `commit` or `rollback` | **passes** |
| **Seam:** `import_lines` batch vs. store | One commit per batch; SQL aligned with normalized insert | `import_lines` commits after loop; `_insert_imported_event` mirrors column set via shared `_EVENT_ANALYTICS_COLUMNS` / `_heckle_event_analytics_params` | **passes** |
| **Failure:** v1→v2 migration exception mid-flight | Rollback, schema version not advanced incorrectly | `init_schema`: `BEGIN IMMEDIATE` + `rollback` on `BaseException` in v1 branch | **passes** |
| **Failure:** `insert_heckle_event_row` child insert fails | Parent + child rolled back together | `except BaseException: conn.rollback()` wraps both statements | **passes** (behavior); **no fault-injection test** — plan §8.4 documents open falsifier |
| **Regression:** `insert_event_row` on v2 schema | Still usable for JSON-only tests / legacy | Inserts `(payload_json, correlation_json)` only; analytics columns nullable on new row | **passes** |
| **Surface 6 (scout):** “JSONL logging” in `pipeline.py` | No stale claim | `rg JSONL heckler/pipeline.py` → no matches at audited tree | **passes** (scout suspicion **ruled out**) |
| **Surface 5 (scout):** lock + long transaction | Migration not inside per-event lock; inserts short | Migration runs in `init_schema` before steady logging; logger lock wraps `insert_heckle_event_row` only | **passes** |

---

## 8. Coverage gap list (Phase 5 — prioritized)

1. **Child-insert fault injection** — Explicitly **open / runtime-armed only** in plan §8.4 and comment in `tests/test_context_buffer_and_logger.py` — **not** a silent contradiction with kill criteria (F-003/F-004 are minor gaps already acknowledged in plan §8.3).
2. **CLI argv surface** — F-003; acceptable if team accepts API-level tests only.
3. **`heckler_eval_labels` existence** — F-004; low risk until writers exist.

---

## 9. Verdict

**`fail`** — **one major** finding (**F-001** `context-map-stale`) per auditor skill severity rules.

**What must be resolved for a strict `pass` re-audit:** Refresh `.dev/plans/sqlite-event-decomposition-analytics/context-map.md` (pre-plan-exploration) at a commit SHA that includes the landed application tree **or** record an explicit orchestrator amendment that retires line-level scout citations in favor of a permanently dual-SHA audit policy (skill currently still classifies staleness as **major**).

**Substantive implementation assessment (non-verdict):** Shared contracts in **plan §2** (types, error envelope, migration posture, logger path, import alignment) are **implemented consistently** at `adc6b2c`; **132** tests passed locally on 2026-05-11.

---

## 10. Scout-prediction reconciliation

| Scout prediction (type) | Description (verbatim / paraphrase from context map) | Outcome | Finding ID |
|---------------------------|--------------------------------------------------------|-----------|------------|
| **suspected_coupling** (Surface 5) | Logger lock vs multi-statement transactions — partial writes if boundaries wrong | **ruled out** for migration-in-lock; logger uses transactional helper | — |
| **suspected_coupling** (Surface 6) | `pipeline.py` still says "JSONL logging" | **ruled out** (no `JSONL` in `pipeline.py` at audited tree) | — |
| **confirmed_coupling** (Surface 3) | `json_extract` dedupe keys ↔ import | **verified** — `COALESCE` + `json_extract` paths aligned with T4 tests | — |
| **confirmed_coupling** (plan §5.4) | Import mirrors `insert_heckle_event_row` SQL / commit semantics | **verified** — batch commit; shared column helpers | — |
| **suspected_coupling** (Surface 4) | Correlation key names for dashboards | **treat-as-prediction** (unchanged this plan; external consumers) | — |
| **ambiguity_flag** Flag 5 | Import / backfill test coverage | **verified** — `tests/test_import_legacy_jsonl.py` landed | — |
| **suspect_modified** `import_lines` test_file empty | Scout claimed no test file | **prediction-divergence** (stale map) | F-001 caveat |

---

## 11. Finding status vs prior revision

*N/A — first audit.*

---

## 12. Phase 1 — Intent traceability (summary)

- **Task statement ↔ code:** Decomposition into relational columns + `event_reactor_results`, automatic v1→v2 migration, logger + import aligned, docs/README/CHANGELOG updated — **aligned**.
- **Non-goals:** No ORM, no new hosted product integration, no full eval UI — **respected**.
- **Map ↔ plan §4:** `heckler/models.py` was **direct** in the map but **not** in packet files-to-touch; **no code change** in `models.py` for this effort — **acceptable scope narrowing** (serialization contract preserved).
- **Packets ↔ diff:** T2–T4 touched files match packets; **T5** packet did not list `CHANGELOG.MD` (observation only). **`tests/test_t20_event_decomposition_architecture_log.py`** comes from **T1** (`b29be7b`), not T2–T5 range — consistent with DAG.

---

## 13. Phase 2 — Contract compliance (summary)

- **`SCHEMA_VERSION` = 2**, **`init_schema`** `RuntimeError` on unsupported future version, **`insert_heckle_event_row`** on logger path, **`insert_event_row`** retained — **matches** §2 *Landed* bullets.
- **Error envelope:** Logger logs and re-raises; `clear_correlation()` in `finally` — **preserved**.
- **Typed config:** No new `HecklerConfig` keys — **matches** T20 / §2.
- **Literal / CLI:** T20 states no new import flags frozen by T1 — **consistent** with existing argparse strings.

---

## 14. Phase 3 — Decision log audit (summary)

- **T20:** Landed flags 1–6 match shipped schema and tests (`test_t20_*`).
- **T21:** Supersession banner matches post-T3/T4 reality; **“Items deferred”** section is historical — **F-006** observation only if readers skip the banner.

---

*Auditor role: report only — no code fixes in this pass.*
