# T21 — Event decomposition schema (SQLite v2)

**Plan:** `sqlite-event-decomposition-analytics`  
**Date:** 2026-05-11  
**Subtask:** T2  
**Upstream:** `.dev/decision-logs/T20-event-decomposition-arch.md`

## Chosen approach

- **`SCHEMA_VERSION` = 2** in `heckler/event_store.py`, with **automatic migration** from version **1** inside `init_schema` (T20 Flag 2).
- **`events`:** additive columns mirroring `HeckleEvent` scalar fields (`utterance_id`, `timestamp_iso`, `transcript`, `semantic_density`, gate booleans, `spoken`, `discard_reason`, `cooldown_remaining_at_eval`, `llm_latency_ms`, `tts_latency_ms`). **`payload_json` / `correlation_json` retained** for JSON round-trip, import (`json_extract` dedupe), and logger compatibility; normalized columns are **backfilled on migration** and are **authoritative for analytics** once writers populate them (T3).
- **`event_reactor_results`:** one row per event when reactor data exists; columns `comment`, `score`, `comment_type`, `raw_response` (1:1 with `ReactorResult`). **Primary key `event_id`** referencing `events(id)` `ON DELETE CASCADE`.
- **`heckler_eval_labels`:** `event_id` FK, `label_name`, optional `label_value`, optional `extra_json`, `created_at` — reserved for dataset-style labels (T20 Flag 3); empty until writers land.
- **Indexes:** `idx_events_utterance_timestamp` on `(utterance_id, timestamp_iso)` for common filter/join patterns and import-adjacent lookups.
- **Migration safety:** `json_valid(payload_json)` guards backfill; invalid JSON rows keep NULL normalized fields and skip reactor extraction. **Single INFO log line** per v1→v2 run.

## Alternatives rejected

- **View-only / no physical columns:** Rejected under T20 Flag 1 (normalized physical SSOT for analytics).
- **Rebuild-only upgrade:** Rejected under T20 Flag 2 (automatic migration required).
- **Flatten reactor into `events` columns:** Rejected under T20 Flag 6 (child table `event_reactor_results`).

## Assumptions made

- **SQLite JSON1** (`json_extract`, `json_valid`, `json_type`) is available (stdlib builds on supported platforms).
- **At most one reactor row per event** matches current pipeline semantics (`Optional[ReactorResult]`).

## Items deferred

- **Populating normalized columns on live insert** — **T3** (`insert_event_row` / logger transaction boundaries).
- **`import_legacy_jsonl.py` dedupe / insert alignment** with normalized columns — **T4** (T20 Flag 5).
- **Doc / string cleanup (“JSONL logging”, eval vocabulary)** — **T5**.

## Files added

- `.dev/decision-logs/T21-event-decomposition-schema.md` (this file; T2 architectural emission).
