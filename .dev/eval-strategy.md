# Heckler evaluation strategy (synthesis)

This note distills persisted-event semantics, gaps, and recommendations for **human-in-the-loop** and **future automated** evaluation of heckler commentary. It assumes the SQLite decomposition described in `heckler/event_store.py` and the README.

---

## 1. What the system already records

- **`events`** — one row per persisted `HeckleEvent`: `utterance_id`, `timestamp_iso`, `transcript`, `semantic_density`, gate flags (`passed_density_gate`, `passed_score_gate`, `passed_pacing_gate`), `spoken`, `discard_reason`, pacing `cooldown_remaining_at_eval`, latencies. Full JSON in `payload_json` for round-trip; normalized columns are the analytics-friendly surface.
- **`event_reactor_results`** — optional child row (1:1 with `events.id` when present): `comment`, `score` (model self-score 0–1), `comment_type`, `raw_response`.
- **`correlation_json`** — LiteLLM / provider correlation (`completion_id`, `model`, etc.) when the reaction path populated tracing context; **`NULL`** on legacy JSONL import.
- **`heckler_eval_labels`** — reserved for dataset-style metadata: `event_id` (FK), `label_name`, `label_value`, optional `extra_json`, `created_at`. **No application writer yet**; safe place for post-hoc human labels without overloading `HeckleEvent` or confusing pacing’s `cooldown_remaining_at_eval` with hosted “eval.”

**Disambiguation:** Pacing uses “eval” in `cooldown_remaining_at_eval`; human or hosted labels belong in **`heckler_eval_labels`**, not in reinterpretation of those columns.

---

## 2. What is *not* recorded today (eval-relevant)

| Gap | Impact |
|-----|--------|
| **Score-gate failures** — reactor returns `(None, …, SCORE_GATE)` when parseable `score < SCORE_THRESHOLD`; pipeline logs `reactor_result=None` | No stored **comment / score / raw_response** for sub-threshold generations. Near-miss mining, threshold tuning, and “model underrated this” are blind. |
| **Context block** — model sees `ContextBuffer` text; only **current** `transcript` is on the event | Callback quality is hard to judge offline without reconstructing order from other rows (lossy vs exact prompt context). |
| **Prompt / config snapshot** — not on the row | Comparing cohorts across prompt edits, models, or `SCORE_THRESHOLD` changes requires external bookkeeping or git archaeology. |
| **Density-gate rejects** — only if `LOG_DENSITY_FAILURES` | No signal on “should not have triggered” for downstream *silence* quality. |
| **Insert failures** — logger re-raises on SQLite failure | Possible **silent tail loss** of events; completeness assumptions for eval are unsafe without monitoring. |

**Semantic nuance:** `spoken=True` means the pipeline took the TTS path successfully, not that a human clearly *heard* the line (levels, environment, clipping).

---

## 3. Recommended label model (`heckler_eval_labels`)

- Attach labels to **`events.id`** (stable row identity), not only `utterance_id`, if multiple lifecycle events per utterance ever appear.
- Prefer a **small controlled vocabulary** to avoid aggregate drift from typos:

  | Concept | Suggested shape |
  |---------|-----------------|
  | Core quality | `label_name = human_quality`, `label_value ∈ positive \| negative \| skip` |
  | `skip` | Abstain: bad transcript, missing context, not worth training on — keeps **negative** clean. |
  | Extensions | Optional tags or notes in `extra_json` (e.g. `rater`, `tags`, free text). |
  | Multi-rater | Multiple rows per `event_id` distinguished by `extra_json` (or future normalized `rater_id`). |

Treat **`event_reactor_results.score`** as model self-report; human labels are **orthogonal**. Interesting slices (once data exists): high model score + human negative; low model score + human positive (requires persisting score-gate candidates).

---

## 4. Labeling workflow and stratification

- **Post-hoc first** — aligns with subjective humor and avoids interrupting the live loop.
- **Stratify exports** to maximize information per labeled row:
  - **`spoken = 1`** — real playback path.
  - **`discard_reason = pacing_gate`** — split into two cohorts (do not treat all rows as “high self-score never aired”):
    - **Post-LLM pacing reject** — `event_reactor_results` child row present; reactor ran and produced comment/score, but TTS was blocked by `PacingGate.evaluate(score)` (score override still applies on this path). Use for pacing vs quality tradeoffs on generated lines.
    - **Pre-LLM pacing reject** — no `event_reactor_results` row, `llm_latency_ms` NULL, no reactor payload; `react()` was skipped during cooldown via `PacingGate.cooldown_status()` (score override does not apply). Use for cooldown volume / LLM-cost analysis, not near-miss commentary; `correlation_json` is typically NULL (no LLM call).
  - **Oversample score boundary bands** (e.g. around `SCORE_THRESHOLD`) — where threshold and prompt changes bite; very high scores are often redundant.
  - **Balance `comment_type`** — avoid overfitting one mode.
  - **Bucket transcript length** — short vs long stresses different failure modes.

Optional later: **active** prioritization using cheap heuristics or an LLM ranker to order a review queue — not as ground truth.

---

## 5. Hosted observability (Langfuse / LangSmith)

- Env-based hooks already documented in README; **`correlation_json`** is the join surface to hosted traces for **live** rows.
- Use human labels to **calibrate** any LLM-as-judge on held-out data; use the judge to **prioritize** review, not replace labels.
- Legacy import rows lack correlation — accept a **split** or avoid cross-store claims for old data.

---

## 6. Adversarial summary (short)

- **Wrong objective risk** — Labels on surviving rows optimize **commentary given the pipeline fired**; they say little about **whether to fire** unless upstream failures and silence are logged or sampled separately.
- **Non-stationary scores** — Self-`score` is not calibrated across model/prompt/time; stratify **within cohort** when possible; add **config/version** stamps per event for fair comparisons.
- **Callback blind spots** — Without persisted context (or a reproducible digest), raters mislabel clever callbacks as nonsense.
- **Label schema drift** — Free-text `label_name` without conventions undermines SQL aggregates; document allowed names or validate at write time.

---

## 7. Prioritized recommendations

1. **Define and use `heckler_eval_labels`** — Implement a small writer (CLI or script): insert rows keyed by `event_id` with the `human_quality` vocabulary and optional `extra_json` for rater.
2. **Optional: persist score-gate candidates** — When enabled (config flag), keep parsed `ReactorResult` for logging even if the pipeline discards for score; populate `event_reactor_results` with `passed_score_gate = 0`, `discard_reason = score_gate`. Unlocks near-miss corpus and human vs self-score disagreement analysis.
3. **Optional: persist context fingerprint or snippet** — e.g. hash of context block + `context_window_size`, or denormalized last-*k* lines (privacy/size tradeoff). Improves callback labeling and reproducibility.
4. **Version stamp events** — At minimum: model id, `SCORE_THRESHOLD`, and a hash or version id of prompt assets (`system.md` / examples). Can start as JSON in `correlation_json` extension or dedicated columns if/when schema bumps.
5. **Export tooling** — SQL view or script: join `events` ⋈ `event_reactor_results` ⋈ optional labels; stratified sampling for CSV/JSON review.
6. **Operational guardrails** — Log or metric SQLite insert failures; periodic row-count sanity vs session length so eval is not fit on a truncated tail.
7. **Calibration slice** — Re-label a fixed small set after major prompt changes to detect rater and automation drift.

---

## 8. Out of scope here

- Changing LiteLLM or Langfuse products themselves; only persistence and join strategy.
- UI for labeling (export + spreadsheet or a minimal internal tool is enough to start).

---

## References in-repo

- Schema and insert path: `heckler/event_store.py`, `heckler/logger.py`, `heckler/models.py`
- Reaction and score gate: `heckler/reactor.py`, `heckler/pipeline.py`
- Legacy data: `scripts/import_legacy_jsonl.py`, README “Legacy JSONL import”
- Architecture / eval table intent: `.dev/decision-logs/T20-event-decomposition-arch.md`, `.dev/decision-logs/T21-event-decomposition-schema.md`
