# T20 — Event decomposition architecture (sqlite analytics)

**Plan:** `sqlite-event-decomposition-analytics`  
**Date:** 2026-05-11  
**Source:** Owner question cards (orchestrator escalation)

## Alignment with shared contract §2 (Types / naming)

- **Binding:** `serialize_heckle_event` / `heckle_event_from_json_dict` remain the **semantic definitions** of `HeckleEvent` field meanings and of any JSON shape used for import and for `payload_json` when it is still written. **SSOT for analytics queries** is the **normalized** tables/columns (and any views defined purely on them). Where both JSON and normalized rows exist, **normalized is authoritative for reporting**; `payload_json` may be redundant or legacy until a documented migration removes it.
- **§2 Naming row:** First-class SQL identifiers for this plan are **frozen here** (T2 may add indexes, constraints, and extra columns only where they do not rename or split these objects without an amendment):
  - **`event_reactor_results`** — optional child row(s) per `events.id` holding exploded `ReactorResult` / nested reactor fields (FK **`event_id`** → `events.id`; exact column set in T21).
  - **`heckler_eval_labels`** — dataset / hosted-style evaluation labels and related metadata joined to events (exact columns in T21; disambiguated from pacing vocabulary per Flag 4).
- **CLI:** No new `import_legacy_jsonl.py` flags are frozen by T1; **T4** owns any future CLI strings per §2 CLI-as-contract rule.

## Files added (executor / audit)

- `tests/test_t20_event_decomposition_architecture_log.py` — regression guard that Flags 1–6 retain explicit **Landed** resolutions (see adversarial note in test module docstring).

## Binding decisions

### Flag 1 — Source of truth (SSOT)

- **Landed:** **Normalized tables/columns are canonical** for analytics-relevant event data. JSON in `payload_json` is **optional, deprecated, or removed only where this log explicitly documents** breaking changes, migration, and operator-facing steps.
- **Non-binding illustration:** Exact table/column list is owned by **T21** (`T2` implementation) and must map 1:1 to `HeckleEvent` / `ReactorResult` semantics unless a follow-up amendment documents intentional divergence.

### Flag 2 — Migration posture

- **Landed:** **Automatic migration** runs as part of store initialization path (`init_schema` or dedicated helpers it calls), with **pytest coverage** including at least one **upgraded on-disk fixture** per major version transition introduced by this work.

### Flag 3 — Eval / labels / prompt metadata

- **Landed:** Eval-adjacent data lives in the **same SQLite file** as pipeline events; **new tables** are allowed. **Join keys** (e.g. `events.id`, `utterance_id`, correlation IDs) must be **named in T21** and mirrored in §2 of the plan after schema lands.

### Flag 4 — Vocabulary: “eval”

- **Landed:** **Both** meanings are in scope: **(a)** post-hoc / dataset / hosted-style evaluation labels and metadata, and **(b)** runtime pacing gate terminology (e.g. `cooldown_remaining_at_eval`). **Docs and SQL object names must disambiguate** (e.g. “pacing eval” vs “dataset eval” / `eval_label` vs pacing columns) — **T5** owns grep + narrative consistency.

### Flag 5 — Import / backfill tests

- **Landed:** **Automated pytest coverage is required** for import/backfill changes in this effort, scoped at minimum to **dedupe `json_extract` paths** and **insert/transaction behavior** touched by decomposition.

### Flag 6 — `reactor_result` physical layout

- **Landed:** **`reactor_result` is stored in a child table** named **`event_reactor_results`** (see §Alignment), keyed to the parent event row via **`event_id`** → `events.id` (column details **frozen in T21**). Nested JSON for reactor fields is **not** the canonical analytics source once the child table lands; any retained JSON must be labeled **redundant** or **legacy** in T21 if still written.

## Explicit non-goals (reaffirmed)

- No ORM layer unless a future plan explicitly supersedes stdlib `sqlite3`.
- No new hosted product integration in this subtask; only **persistence** choices.

## Downstream owners

| Artifact | Owner |
|----------|--------|
| DDL + `SCHEMA_VERSION` + auto-migration code | T2 → `.dev/decision-logs/T21-event-decomposition-schema.md` |
| Logger write path + transaction boundaries | T3 |
| `import_legacy_jsonl.py` + tests | T4 |
| Doc disambiguation + retired strings | T5 |
