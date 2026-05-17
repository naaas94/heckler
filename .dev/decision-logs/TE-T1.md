# TE-T1 — Transcript SQLite schema (transcription-engine)

> **Landed / supersession (plan v1.1, audit F1 — closed in T6):** `export_session_markdown` is **implemented** in `heckler/transcript_store.py` (subtask **T2**). **Items deferred** documents **Landed in T2** explicitly so auditors do not read a pre-T2 “exporter absent” posture (persona-system audit **FIND-02** class).

**Subtask:** T1 · **Plan:** transcription-engine v1.1 · **Date:** 2026-05-16

## Chosen approach

- New module `heckler/transcript_store.py` owns DDL and CRUD for `transcript_sessions`, `transcript_chunks`, and singleton `transcript_schema_version` (version `1`), separate from `heckler_schema_version` / `init_schema` in `event_store.py`.
- Callers obtain connections via existing `heckler.event_store.open_store` (WAL, `foreign_keys=ON`, busy timeout, parent `mkdir`) and call `init_transcript_schema` on that connection; no duplicate connection factory in `transcript_store`.
- Chunk rows reference `transcript_sessions(id)` only (no FK to `events`); transcript IDs are a parallel namespace from utterance/event IDs per plan Flag 1.

## Alternatives rejected

- **Extend `event_store.py`:** Would couple `SCHEMA_VERSION` / migration policy to transcript tables that are unrelated to `HeckleEvent` analytics; rejected in favor of a dedicated module and `TRANSCRIPT_SCHEMA_VERSION`.
- **Separate SQLite file for transcripts:** Simpler isolation but diverges from T20 same-file eval/transcript posture and duplicates backup/ops paths; rejected in favor of shared path with isolated version table and DDL.

## Assumptions

- Single-process heckler use with WAL matches today’s event logger pattern; `CREATE TABLE IF NOT EXISTS` on both init paths avoids destructive races for v1.
- `open_store` remains suitable for transcript connections without modification (T1 kill criterion).

## Items deferred

- **`export_session_markdown`:** **Landed in T2** — `heckler/transcript_store.py` now implements `export_session_markdown`; T1 intentionally excluded it (schema + CRUD only).
- Forward migrations when `TRANSCRIPT_SCHEMA_VERSION` bumps are not implemented; `init_transcript_schema` raises `RuntimeError` if stored version is below or above the supported constant until a future migration subtask exists.
