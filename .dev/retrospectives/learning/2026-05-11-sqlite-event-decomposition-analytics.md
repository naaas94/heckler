# Retrospective — Learning: sqlite-event-decomposition-analytics

**Date:** 2026-05-11  
**Artifacts reviewed:** `.dev/plans/sqlite-event-decomposition-analytics/plan.md`, `context-map.md`, packets T1–T5, `.dev/decision-logs/T20-event-decomposition-arch.md`, `.dev/decision-logs/T21-event-decomposition-schema.md`, `.dev/audits/2026-05-11-sqlite-event-decomposition-analytics.md`

---

## 1. Task context

**What shipped (at application SHA `adc6b2c…`, per plan §8.1):** SQLite `events` gained analytics-oriented columns plus `event_reactor_results` and reserved `heckler_eval_labels`; `SCHEMA_VERSION` moved to 2 with automatic v1→v2 migration; the live logger path writes through `insert_heckle_event_row` (parent + optional reactor child in one transaction); legacy `insert_event_row` stayed for JSON-only callers; `import_legacy_jsonl.py` stayed aligned with the normalized insert shape and dedupe keys; tests and docs moved with it. **Why this qualifies for learning:** it was a full persistence contract change—DDL, migration, two writers (logger + import), and explicit SSOT rules across JSON and relational surfaces—not a localized refactor.

---

## 2. What I now understand that I didn’t before

**Normalized SSOT alongside redundant JSON is a deliberate product shape, not a halfway state.** T20’s landing—“normalized tables/columns are canonical for analytics; `payload_json` may be redundant or legacy until a documented migration removes it”—makes the mental model crisp. Analytics queries should not infer semantics from JSON blobs when scalar columns exist; JSON remains for round-trip, import dedupe (`json_extract`), and transitional callers. That split is easier to reason about than pretending one storage form “wins” everywhere.

**The highest-leverage planning move was freezing architecture before anyone touched DDL.** The architecture decision log (T20 — owner answers on SSOT, migration, eval storage, reactor physical layout, import test policy, vocabulary) turned a CONDITIONAL context map into executable packets. Downstream work (T2 — schema and migration in `event_store`, T3 — logger transactional write path, T4 — import alignment and tests, T5 — doc and retired-string sweep) could proceed without re-negotiating fundamentals in the middle of a diff.

**“Hidden coupling” rows in the plan were load-bearing and one of them was exactly right.** The plan’s worry that `import_legacy_jsonl` must mirror `insert_heckle_event_row` commit semantics and column shape wasn’t paranoia—it’s the seam where ETL and runtime writers diverge silently. Shipping shared column/param helpers (as reflected in the audit’s integration review) is the mechanical fix; **tests that treat import and store as one contract** are what keep that fix from rotting.

**A superseded decision log is not a bug if the banner is the contract.** T21 (schema choices for v2) still lists “items deferred” for live insert population, import alignment, and doc cleanup—work that T3/T4/T5 later completed. Reading only the deferred list would mislead; reading the supersession banner first restores truth. That’s a general pattern: **append-only design history plus an explicit “authoritative surface is code + these tests” header** beats rewriting history and losing the rejected-alternatives record.

**Audit vs. plan language on staleness:** documenting in plan §0 that the pre-plan context map commit lags HEAD does not satisfy a strict auditor provenance rule—the audit still recorded a major `context-map-stale` finding. So “we warned ourselves in prose” and “archive integrity” are different goods. For future me: either refresh the map at the completion SHA or accept that some audit passes will `fail` on provenance while still saying the code story is sound.

---

## 3. Decisions I made and would make again

**Serializing T2 → T4 instead of parallelizing import work with schema work.** The plan explicitly rejected unsafe parallelism on DDL-consuming code; keeping schema (T2) ahead of import (T4) reduced merge and contract drift risk. Same principle next time: **parallelize only where the dependency graph proves independence**, not where it “feels” independent.

**Automatic migration with a real on-disk fixture in pytest (T20 Flag 2).** Betting on operators to rebuild DBs doesn’t scale; automatic `init_schema` migration plus migration tests matches how SQLite apps actually live in the wild.

**Child table for `reactor_result` instead of flattening into `events`.** Keeps nullability and column explosion manageable and matches “at most one reactor row per event” semantics without widening the hot row for every event.

---

## 4. Decisions I made that I would change

**Nothing in the shipped architecture I’d unwind without new requirements.** Process-wise, I’d **refresh or re-pin the context map to the application SHA** (or trim line-level scout predictions earlier) so the first audit isn’t structurally guaranteed to emit F-001-style noise. That’s hygiene, not regret about the persistence design.

**Scout grep inventory:** the audit noted `insert_heckle_event_row` missing from the pre-plan coupling grep list even though post-plan §5.4 depended on it. Next pre-plan pass: **include every symbol the plan will later name as a seam**, not only the obvious legacy names.

---

## 5. Patterns in my own thinking

**I’m correctly skeptical of “single mega-subtask” persistence work**—the plan’s rejected alternative (“do all persistence work” in one chunk) would have maximized silent contract drift. The decomposition by **decision freeze → schema → logger → import → docs** matched how uncertainty actually clustered.

**Risk calibration:** the plan flagged T2 (schema + migration) as highest re-plan risk; in hindsight migration and transaction boundaries were handled carefully and the adversarial pass green-lit the scary seams. **Trouble didn’t come from the predicted hotspot alone**—stale map / provenance surfaced as the loud audit signal instead. Useful reminder: **process artifacts age at a different rate than code**.

---

## 6. Open questions

- When (if ever) is it worth **dropping or slimming `payload_json`** on the live path, and what migration + operator story makes that safe without breaking import and round-trip tests?
- **Fault injection** for “child insert fails → parent rolled back” is documented as an open falsifier—how much runtime-only risk am I willing to carry vs. investing in a small sqlite hook or mock-based test?
- **`heckler_eval_labels`** is reserved with no writer—what’s the first real writer story (who sets `label_name`, retention, correlation to hosted eval IDs)?

---

## 7. Single paragraph synthesis

This task reinforced that **persistence evolution succeeds when architecture is frozen in writing before DDL lands**, when **import and runtime writers share one insert contract** (enforced by helpers and tests, not by hope), and when **SSOT is allowed to differ by concern**—normalized columns for analytics, JSON for interchange and legacy—without pretending they must collapse into a single representation prematurely; the audit’s sting on **stale context-map SHA** was a separate lesson that **honest documentation of staleness is not the same as audit-grade provenance**, so next time I should either refresh the map at the handoff commit or budget a provenance-class finding as expected noise.
