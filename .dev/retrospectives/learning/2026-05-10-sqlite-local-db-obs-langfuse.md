# Learning retrospective — sqlite-local-db-obs-langfuse

Personal notes — `.dev/retrospectives/learning/`. Sources: `.dev/plans/sqlite-local-db-obs-langfuse/plan.md` **v1.1.0**, `context-map.md`, packets T1–T6, `.dev/decision-logs/T12.md`–`T15.md`, `CHANGELOG.MD` (sqlite-local-db-obs-langfuse), `.dev/retrospectives/methodology/2026-05-10-sqlite-local-db-obs-langfuse.md`, `.dev/audits/2026-05-09-sqlite-local-db-obs-langfuse.md` (referenced by methodology retro), implementation skim: `heckler/event_store.py`, `heckler/tracing_context.py`, `heckler/logger.py`, `heckler/reactor.py`.

---

## 1. Task context

- **Task:** sqlite-local-db-obs-langfuse — replace steady-state JSONL event logging with **SQLite** (`stdlib sqlite3`), unify event JSON on **`serialize_heckle_event`**, add **reactor-local** LiteLLM observability (**`metadata`** when env indicates Langfuse/LangSmith-style tracing) and **`tracing_context`** so DB rows can carry **correlation_json**, optional **`scripts/import_legacy_jsonl.py`**, docs and tests. Plan status **Complete** per plan §0 / §8 narrative; subtasks **T1–T6** with four **architectural** decision logs (T12–T15).
- **Dates:** Exploration and owner decisions **2026-05-09**; execution/closure **2026-05-09**; this note **2026-05-10**.
- **Why a learning retrospective (not only methodology):** The work joins **persistence threading**, **cross-cutting serialization contracts**, and **third-party observability** without taking a hard dependency on Langfuse SDKs. The context map explicitly separated ambitious wording (“database for observability… Langfuse”) from what shipped: **local rows + call-site scaffold**. That scoping move, plus the **single-connection + lock** SQLite pattern and the **reject global LiteLLM callbacks** choice (T15), is worth keeping as reusable engineering judgment—not just process.

---

## 2. What I now understand that I didn’t before

**SQLite in a threaded pipeline is a policy bundle, not “swap the file backend.”** WAL + `synchronous=NORMAL` + `busy_timeout` + **`check_same_thread=False`** only work if you also own **writer serialization**. Here that is the existing **`HecklerLogger` lock** (T12/T14): one shared connection, explicit mutual exclusion on inserts. I had a fuzzy notion that “SQLite is fine single-process”; the durable picture is **pragma set + connection lifetime + who may call execute concurrently**.

**Bridging “completion returned” to “row inserted” without async context:** **`threading.local()`** correlation (T12) is the minimal glue when **`react`** and **`log_event`** run on the **same reaction worker thread** and you refuse to widen `HeckleEvent` for trace IDs in v1. It stays correct only while that thread assumption holds—plan §5.2 called that out; if logging ever hops threads, this pattern breaks silently unless replaced (e.g. explicit IDs on the event or `contextvars` with deliberate propagation).

**Hosted tracing without importing Langfuse in heckler:** Passing LiteLLM **`metadata`** (`generation_name`, `tags`) when env keys suggest tracing (T15), while **not** mutating **`litellm.success_callback`**, keeps optional integrations **operator-driven** and avoids duplicate trace roots and accidental hard deps. I now file that under: **prefer call-site kwargs + env over framework monkey-patches** for small apps wrapping LiteLLM.

**Duplicate serializers were latent schema drift.** The context map Surface 3 (logger `_serialize` / `_coerce_json` vs `serialize_heckle_event`) was not theoretical—unifying on **`json.dumps(serialize_heckle_event(event))`** (T14) makes **`tests/test_models.py`** the shape authority for persisted JSON. “One projection for DB and round-trip tests” is a pattern I’ll reuse anywhere logs and models both exist.

**Ambitious product language needs an explicit narrowing step.** The raw task spoke of eval, funniness, and “store everything”; the map’s **owner decisions** pinned **no audio in DB**, **scaffold-only eval**, **`litellm.completion` as the sole tracing surface**. The shipped system is coherent because that narrowing happened **before** §2 contracts—not as post-hoc rationalization.

**Plan §5.3 (T3 as highest re-plan risk) described a real hazard class; what hurt in practice was often meta.** The methodology retrospective notes integration/tests held, while **closure hygiene** (§8 tree SHA mismatch, stale T13 interim-JSONL prose, first audit on wrong tree) created friction. Lesson split: **T3-shaped seams** are still where row-shape bugs hide; **documentation/provenance** is where merge gates can fail even when code is fine.

---

## 3. Decisions I made and would make again

- **Stdlib `sqlite3` first, no SQLAlchemy for a single `events` table** — matches single-process heckler and keeps the persistence story inspectable in plain SQL (T12; plan §5.1 rejected SQLAlchemy-first).
- **`correlation_json` column + optional blob** rather than stuffing trace fields into `HeckleEvent` in v1 — preserves domain model cleanliness while allowing SQLite joins later.
- **Clear correlation in `finally` on `log_event`** (T14) — prevents stale IDs bleeding into the next event; small lifecycle detail with large correctness payoff.
- **Reject `litellm.success_callback = ["langfuse"]` globally** (T15) — avoids process-wide mutation and surprise imports.
- **T6 as optional script under `scripts/` without `project.scripts`** — honors CLI freeze in §2 and keeps packaging surface minimal.
- **Decomposition T1/T2 parallel, then logger + reactor** — matched file ownership and kept kill criteria separable (plan §5.1 mega-task rejection looks right in hindsight).

---

## 4. Decisions I made that I would change

- **§8 “tree SHA at closure” not verified against the commit that actually contains new artifacts** — methodology retro **D1**; better rule: **automate or checklist** “first commit introducing `event_store.py` / tag HEAD” before marking plan Complete.
- **T13 decision log left interim JSONL narrative after T3 removed it** — stale “Chosen approach” undermines trust in logs as audit inputs; **post-land pass on architectural logs when later subtasks change the story** should be part of T5 DoD.
- **First adversarial audit on wrong/uncommitted tree (audit v1 F1)** — process failure, not design; **always record audited `git rev-parse HEAD` and dirty state** in the audit header before Phase 2.

Underlying errors: **treating closure metadata as best-effort**, and **assuming decision logs self-heal** without a forced sync when the changelog narrative moves.

---

## 5. Patterns in my own thinking

- **Over-weighting “green tests + good §2” as sufficient for merge readiness** — the SQLite plan showed **provenance and log prose** still gate quality; tests didn’t catch wrong SHA or stale T13.
- **Correct instinct to narrow “Langfuse in SQLite”** via owner decisions — the risk would have been building **fake causality** (SQLite as trace backend) instead of **join keys** (local correlation + hosted traces via LiteLLM).
- Possible **under-investment in executor-triggered doc sync** relative to code velocity — same pattern as heckler-v1 learning retro (decision logs lag amendments).

---

## 6. Open questions

- When to add **explicit `Connection.close()`** on shutdown (T14 deferral) vs relying on process exit—what’s the smallest leak-free hook in `pipeline.main` without new threading races?
- If schema grows beyond **`events`**, is a **tiny migration runner** still cheaper than SQLAlchemy, or does table count flip the decision?
- **Live** verification against Langfuse/LangSmith (networked) — worth a one-off manual recipe or a skipped integration job in CI?
- **`--skip-existing`** depending on JSON1 (T6): how often do Windows/Python builds ship SQLite **without** JSON1, and should the script probe and degrade gracefully?
- If **`log_event`** ever moves off the reaction thread, does **`threading.local`** get replaced by **`contextvars`** set around the whole reaction span, or by IDs on `HeckleEvent`?

---

## 7. Single paragraph synthesis

This task clarified that **replacing JSONL with SQLite in a threaded app is a concurrency and contract problem**: WAL pragmas plus a single shared connection only work with a **clear writer-lock story**, and **trace correlation** across LiteLLM and persistence is best handled as **thread-local metadata cleared in `finally`**, not as duplicate serializers or global LiteLLM callbacks. The compounding lesson is architectural and procedural: **narrow vague observability goals before coding** (local DB rows vs hosted traces), **bind persisted JSON to one serializer** shared with tests, and **treat plan closure SHA and decision logs as part of the shipped artifact**—otherwise adversarial review catches merge blockers that green tests never will.

---

*Filed per retrospective-learning skill; narrative grounded in artifacts consumed 2026-05-10.*
