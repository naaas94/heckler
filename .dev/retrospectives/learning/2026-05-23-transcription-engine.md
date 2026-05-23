# Retrospective — learning · transcription-engine (deep)

**Date:** 2026-05-23 (re-read of 2026-05-16 execution + post-closure repo state)  
**Task:** Heckler **transcribe-only mode** — parallel SQLite transcript sessions/chunks, config + VAD overrides, `pipeline.main` mode split, CLI `--mode` / `--session-name`, markdown export, integration tests; plan **v1.1** + amendment **T6** (provenance repair).  
**Why this qualifies:** Architectural-tier persistence and pipeline split; a **failed-then-repaired** orchestrator handoff; the feature became **load-bearing infrastructure** for gui-launcher and `PipelineController` without a second schema pass.

**Artifacts reviewed (2026-05-23):**

| Layer | Paths |
|-------|--------|
| Plan / packets / map | `.dev/archive/transcription-engine/plan.md`, `context-map.md`, `packets/T1.md`–`T6.md`, `transcription-engine.md` (design) |
| Process | `.dev/audits/2026-05-16-transcription-engine.md` (rev 2 **pass**), `.dev/retrospectives/methodology/2026-05-16-transcription-engine.md`, `2026-05-23-transcription-engine.md` |
| Decisions / changelog | `.dev/decision-logs/TE-T1.md`, `TE-T4.md`, `CHANGELOG.MD` § transcription-engine |
| Code / tests | `heckler/transcript_store.py`, `heckler/config.py`, `heckler/pipeline.py`, `heckler/controller.py` (downstream), `tests/test_transcript_store.py`, `tests/test_config.py`, `tests/test_pipeline.py` |
| Git | T1 `8439bb83` → T6 `026d68d6`; archive move `bb7746aa`; current `HEAD` `adcbec9b` |

**Prior learning note:** `.dev/retrospectives/learning/2026-05-16-transcription-engine.md` — this file supersedes it in depth; keep both if you want a contemporaneous vs. cooled read.

---

## 1. Task context

**What shipped.** A second pipeline personality inside the same entrypoint: **`--mode transcribe`** (or `HECKLER_MODE=transcribe`) runs **AudioCapture → Whisper → `transcript_store`** only. Persona mode still runs capture → transcribe → density → reactor → pacing → TTS → `HeckleEvent` logging. Transcribe mode never constructs Reactor, Speaker, gates, or `HecklerLogger`; it never calls `init_schema` on the event side in the same `main()` invocation.

**Persistence model.** New tables `transcript_sessions`, `transcript_chunks`, version row in `transcript_schema_version` — same SQLite **file** as events (`config.sqlite_database_path`), **no FK** to `events`, separate version constant from `heckler_schema_version`. Markdown export writes `{transcripts_dir}/{session_label}.md` via atomic `os.replace`.

**Plan arc.** Six executor subtasks (T1 store, T2 exporter, T3 config, T4 pipeline + CLI, T5 integration tests, T6 audit remediation). v1.0 claimed §8 **Complete** while the plan tree was **untracked** and §8.1 cited a SHA that did not contain those paths (**audit P1/P2**). v1.1 **T6** committed `.dev/plans/transcription-engine/**`, reflexive §8.1, map §Phase 0.5 baseline, TE-T1 supersession banner; re-audit **pass** at **`026d68d6`**.

**After “done.”** The plan tree was **renamed** to `.dev/archive/transcription-engine/` in `bb7746aa` (content preserved; §8.2 path literals in the frozen plan still say `.dev/plans/...`). **gui-launcher** and **PipelineController** reused `_run_transcribe_worker`, `transcript_store`, and the mic-gate pattern without reopening the transcription-engine DAG. The archive design doc (`.dev/archive/transcription-engine/transcription-engine.md`) still says **“Design — not yet implemented”** — FIND-02-class stale prose the T6 sweep did not touch.

**Verification today.** At `HEAD` (`adcbec9b`): `git show HEAD:.dev/archive/transcription-engine/plan.md` succeeds; `git show HEAD:.dev/plans/transcription-engine/plan.md` **fails**. Transcribe-focused pytest subset: **32 passed** (`test_transcript_store`, transcribe-related `test_config` / `test_pipeline`).

---

## 2. What I now understand that I didn’t before

### 2.1 Domain: two products sharing a mic, not one pipeline with a flag

Heckler’s persona loop optimizes for **short, reactive utterances** and **filters** low-density speech. Transcribe mode optimizes for **archival completeness** — no density gate, no reaction queue, no TTS-driven mic suppression. Treating transcribe as “persona with components turned off” would have dragged the wrong abstractions (e.g. stuffing chunks into `HeckleEvent`). The plan’s Flag 1 resolution — **parallel ID namespaces** (session UUID vs `utterance_id`) — is the right mental model: one backup file, two **stories** that only correlate by timestamp if you choose to join them later.

**VAD is mode-specific product behavior, not a global constant.** Persona defaults (15s max speech, 800ms silence) fight long-form capture. Transcribe overrides (45s, 1500ms, 250ms min) belong on **`HecklerConfig`** as `transcribe_*` fields and reach **`AudioCapture` only** via `dataclasses.replace` on a frozen config — `Transcriber` keeps base config so Whisper settings do not accidentally inherit VAD timing meant for segmentation.

### 2.2 Stack: composition patterns that survived audit and reuse

**`threading.Event()` as a stand-in for `Speaker.is_playing`.** `AudioCapture` only calls `is_playing.is_set()`. A never-set Event means “TTS not playing” forever → mic always eligible. This is duck typing on a **synchronization primitive**, not on Speaker — worth remembering whenever a subsystem assumes a concrete owner type.

**`open_store` reuse without `init_schema` in transcribe `main`.** Transcript DDL uses `init_transcript_schema` on a connection from `event_store.open_store`. Persona path uses `HecklerLogger` → `init_schema`. In shipped code they **do not run in the same process invocation** for transcribe mode, so the §5.4 “dual init on one `main()`” fear is **theoretical** until a hybrid mode exists — but the **documented** kill criterion (don’t touch `SCHEMA_VERSION`) kept event migrations from absorbing transcript tables.

**Worker symmetry.** `_run_transcribe_worker` mirrors `_run_transcription_worker`’s queue/sentinel loop but writes `insert_chunk` under a **dedicated lock** instead of enqueueing to `reaction_queue`. Overflow policy stays on the **enqueue** side (`_put_drop_oldest` in capture); the transcribe worker only drains — a subtle split easy to get wrong if you add a second queue discipline.

**Export semantics vs operator experience.** `export_session_markdown` can raise; pipeline/controller **log and swallow** on shutdown so Ctrl+C still closes the session. That trades **hard failure** for **always-finish** — a product choice TE-T4 defers rather than hiding.

**Callback hook for GUI without breaking CLI.** Later work added `on_transcript: Optional[Callable]`; when `None`, `[TRANSCRIBE]` prints remain. That pattern — **preserve default stdout behavior when callback absent** — is how backend plans can stay CLI-first while gui-launcher becomes the integration surface Flag 3 deferred.

### 2.3 Process: provenance as part of the deliverable

**Green pytest ≠ binding handoff.** v1.0 had working code at `b943195` and still failed audit on **P1** (plan bundle not in the index) and **P2** (§8.1 SHA did not resolve cited paths; that SHA was even a **persona-system** commit — wrong tree entirely). I now treat **`git ls-files` + `git show <handoff-sha>:path`** for every §8.2 row** as the same class of “done” as tests, whenever the orchestrator promises archaeology.

**Reflexive SHAs (`git log -1 --format=%H -- <plan path>`) are the fix for P2.** Any pasted hash in prose is a liability across amend, cherry-pick, or parallel plans on one branch.

**Context maps need two time axes.** Scout SHA `7b5382e` was correct **for exploration** and wrong **as a live comparator** after implementation. Map v1.1’s §Phase 0.5 rule (baseline = bundle introducer; scout = historical) is how you keep navigation hints without lying about staleness — the persona-system audit **FIND-01** class.

**“Deferred” prose rots (FIND-02).** TE-T1 still listed exporter as deferred after T2 landed until T6’s supersession banner. Stale deferrals train auditors and future-you to distrust decision logs.

**Closure at SHA ≠ closure at arbitrary `HEAD`.** After `bb7746aa`, plan §8.2 still lists `.dev/plans/transcription-engine/...` but the canonical tree is **archive**. CHANGELOG still links the old path. **Truth is commit-pinning:** detach at `026d68d6` for the bundle introducer’s literal paths, or read **archive** paths at current `HEAD` — mixing the two without thinking produces false “handoff broken” alarms.

### 2.4 Downstream: transcription-engine as platform, not a dead-end CLI flag

gui-launcher did not redesign persistence; it **moved lifecycle** into `PipelineController` (`_start_transcribe_mode`, `load_models(mode="transcribe")` skipping Speaker, session end status with markdown path). The transcription-engine plan explicitly deferred PyQt6 (Flag 3); the learning is that **deferring UI but shipping store + worker + CLI** was the right cut — the controller plan could treat transcribe as a **known subsystem** with stable contracts (`insert_chunk`, `close_session`, `export_session_markdown`, bare `Event` for mic gate).

---

## 3. Decisions I made and would make again

| Decision | Principle | Why it still looks right |
|----------|-----------|---------------------------|
| **`transcript_store.py` instead of extending `event_store`** | Separate migration/version policy per domain | TE-T1’s rejected alternative would have coupled analytics schema bumps to transcript DDL |
| **Same DB file, separate `TRANSCRIPT_SCHEMA_VERSION`** | One backup path (T20 posture), isolated evolution | Operational simplicity without entangling `HeckleEvent` |
| **Mode dispatch only in `pipeline.py` / controller** | Single orchestration owner | `config.mode` is not read in `audio_capture` or `transcriber` — grep-clean boundary |
| **Skip lazy imports; skip construction** | Pay cost where it matters | Kokoro/LLM load at `Speaker`/`Reactor` **init**, not import — falsifier tests with constructor stubs are sufficient |
| **`dataclasses.replace` for VAD overrides** | Immutable config + derived effective config | Avoids a second mutable config type or env reread in capture |
| **T6 scoped `git add`** | Minimize unrelated `.dev/` churn | Unblocked P1 without sweeping deleted archives |
| **Explicit F4 deferral in CHANGELOG** | Waived gaps must be visible | Audit **G1** waived with consent, not silence |
| **Atomic markdown write (temp + `os.replace`)** | Crash-safe snapshots | Matches seriousness of “archival” use case |

---

## 4. Decisions I made that I would change

| Decision / omission | Underlying error | Better rule next time |
|-------------------|------------------|----------------------|
| **§8 “Complete” on v1.0 without §8.2 matrix** | Conflated narrative closure with git object graph | No Complete until every binding path passes `git show` at cited SHA on a **clean** tree |
| **Pasted §8.1 SHA (`809ba45`)** | Copy-paste / wrong commit family | Only reflexive SHAs, or run `git cat-file -e` per path immediately before writing §8 |
| **TE-T4 header left at “v1.0” after v1.1** | T6 hygiene scope too narrow | Any remediation pass that touches TE-T1 should **normalize all TE-* headers** in the same commit |
| **Archive move without plan/CHANGELOG path pass** | Treated rename as “git hygiene,” not contract drift | When moving `.dev/plans/*` → `.dev/archive/*`, add a **micro-amendment** or footer: “paths at `HEAD` → archive prefix; bundle SHA `026d68d`” |
| **Left design doc “not yet implemented”** | Scoped T6 to plans + TE-T1 only | FIND-02 sweep should include **`.dev/archive/.../transcription-engine.md`** when the feature is shipped |
| **Tiered T6 as `standard`** | Underestimated blast radius | Label provenance / §8 closure subtasks as **architectural** or tag `binding-artifacts` in the packet title |

---

## 5. Patterns in my own thinking

**Over-weighting implementation merge.** I treated merged `heckler/*` + pytest as the finish line. The orchestrator workflow’s finish line for contract-first work includes **indexed plans** — a blind spot until the adversarial audit.

**Under-weighting cross-plan commit noise.** Interleaving persona-system commits on the same branch made it easy to grab the **wrong SHA** for §8.1 (a persona T6 commit id). Branch hygiene or explicit “bundle introducer” commits matter for archaeology, not just for code review.

**Comfort with deferred items in decision logs.** “Exporter deferred in T1” felt accurate **at T1 time** but became **misinformation** after T2. I should treat decision logs as **current-state documents**, not diaries — supersede or strike through when landings happen, not only at audit time.

**Motivated completion on §8.** Wanting a clean story without committing `.dev/plans/**` or re-running checks — the friction was signal that the handoff was incomplete.

**Right trust in adversarial §5 for technical risk.** §5.3 worried about T4 (VAD, imports); audit majors were **process**. Technical decomposition (T1/T4 architectural logs, falsifier tests) paid off; **process decomposition (T6)** was necessary but initially under-resourced.

---

## 6. Open questions

1. **Hybrid mode** (persona reactions + transcript persistence in one run): Is serial `init_schema` then `init_transcript_schema` on one connection enough, or do we need a shared init coordinator and documented lock ordering?

2. **`HECKLER_MODE` env validation:** Should invalid values hard-fail, map to persona, or stay “garbage in → persona” forever? F4 was deferred with audit waiver — is that still acceptable for GUI-only operators who never pass `--mode`?

3. **Path-stable §8.2:** Should archived plans carry a machine-readable `canonical_path_prefix` and `bundle_introducer_sha` so `git show` checks work at any future `HEAD` without mental translation?

4. **Persona `_run_transcription_worker` tests:** Still out of scope per Flag 5 — does transcribe coverage give enough confidence for shared queue/sentinel behavior, or will persona regressions stay blind until someone adds direct tests?

5. **Streaming partial transcripts:** Design doc defers `whisper_streaming`; chunk-based VAD end detection sets latency floor for “live feed” UX — when does that become a product requirement?

6. **Audit rev 1 archaeology:** Rev 1 text not in git — is local/IDE history enough for long-term process learning, or should failed audits be committed as `*-rev1.md`?

---

## 7. Single paragraph synthesis

Transcription-engine taught me that **a correct transcribe path in code is only half the deliverable** in a contract-first workflow: **binding artifacts must exist in git at the handoff SHA**, context maps must separate **scout history** from **live baseline**, and decision logs must **supersede “deferred” items when they land**. Technically, the durable patterns are **parallel SQLite namespaces** in one file, **`dataclasses.replace` on frozen config for mode-specific VAD**, a **never-set `threading.Event`** for mic gate without Speaker, and a **transcribe worker that only drains** the same overflow policy capture enforces — patterns that gui-launcher could reuse without reopening schema design. The compounding mistake to avoid is declaring orchestrator §8 **Complete** while `git show HEAD:.dev/plans/.../plan.md` would fail; the compounding habit to keep is **reflexive bundle SHAs**, **scoped remediation commits**, and reading archived plans at **`.dev/archive/...`** when the repo has moved on from `.dev/plans/...`.

---

## Appendix — quick reference (six-month future self)

**Run transcribe (CLI):** `python -m heckler --mode transcribe [--session-name NAME]`  
**Bundle introducer (plan in git at T6):** `026d68d6dfd3507f7c4debf93a1cf94ad6ea0239`  
**Read plan today:** `.dev/archive/transcription-engine/plan.md`  
**Decision logs:** `.dev/decision-logs/TE-T1.md`, `TE-T4.md`  
**Audit:** `.dev/audits/2026-05-16-transcription-engine.md` (**pass** rev 2)  
**Methodology twin:** `.dev/retrospectives/methodology/2026-05-23-transcription-engine.md`
