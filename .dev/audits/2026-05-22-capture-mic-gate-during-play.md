# Audit — capture-mic-gate-during-play

**Audit document revision:** 1 (initial)  
**Date:** 2026-05-22  
**Plan version:** 1.0  
**Auditor focus:** Integration seams (§Coupling surfaces), concurrency on `is_playing` clear edge, contract typed-surface admission for `play_gate_frame_tick`  
**Audit anchor SHA (code/contracts):** `504ca11319c952c4317a795a1ab4707446bd7b85` (T2)  
**Repository HEAD at audit time:** `0da7ac5232d88e190906f967f0f3ffdc339d4691` (includes post-plan `pacing-before-llm`; capture files identical to anchor)

---

## 1. Audit metadata

| Field | Value |
|-------|-------|
| Task name | capture-mic-gate-during-play |
| Context map path | `.dev/plans/capture-mic-gate-during-play/context-map.md` |
| Readiness at planning | CONDITIONAL |
| Phase 0 discipline | Completed before narrative artifacts (task §1, plan §2, `audio_capture.py`, `tests/test_audio_capture.py` only; plan §0+§8 read afterward for provenance) |
| pytest | `pytest tests/test_audio_capture.py -q` → **11 passed** (2.53s) at HEAD |
| Capture code delta anchor→HEAD | **none** (`heckler/audio_capture.py`, `tests/test_audio_capture.py` unchanged since `504ca113`) |

---

## 2. Provenance log

| Check | Result |
|-------|--------|
| Context map scout SHA | `e3fd9dc5c58278f46e3d5729f214927db5dd3dcd` (clean tree) |
| Handoff / T2 SHA | `504ca11319c952c4317a795a1ab4707446bd7b85` |
| Audit HEAD SHA | `0da7ac5232d88e190906f967f0f3ffdc339d4691` |
| SHA comparison (scout → anchor) | **diverged** on in-scope implementation/docs (see below) |
| SHA comparison (anchor → HEAD) | **match** for `heckler/audio_capture.py`, `tests/test_audio_capture.py`, `heckler/controller.py`, `heckler/speaker.py` |
| Working tree at audit | **dirty** — `M .dev/plans/capture-mic-gate-during-play/plan.md` (§8 appended locally); unrelated archive/plan deletions and `transcripts/` untracked |

**Diverged files (scout SHA → anchor `504ca113`, in §File map scope):**

- `heckler/audio_capture.py` (expected — T1)
- `tests/test_audio_capture.py` (expected — T1)
- `heckler_seed.md`, `CHANGELOG.MD`, `README.md` (expected — T2)
- `.dev/plans/capture-mic-gate-during-play/*` (added at T2)

→ `context-map-stale` filed (major, process); code findings on landed capture behavior are verified at **anchor SHA**, not scout SHA.

**Scout grep coverage:** All patterns listed in context-map §Coupling surfaces are present; no `scout-incomplete` finding.

**Plan-artifact provenance (`git show 504ca113:<path>`):**

| Artifact | In `504ca113` | On disk (audit) | Notes |
|----------|---------------|-----------------|-------|
| `context-map.md` | present-in-HEAD | present | Scout SHA stale vs anchor |
| `plan.md` | present-in-HEAD | present | **§8 body = "Not produced" in HEAD**; working tree has full §8 (uncommitted) |
| `packets/T1.md` | present-in-HEAD | present | OK |
| `packets/T2.md` | present-in-HEAD | present | OK |
| `capture-mic-gate-during-play-T1.md` | present-in-HEAD | present | OK |
| `tts-mic-gate-tail-T2.md` (supersession) | present-in-HEAD | present | OK |

**Closure SHA:** Plan working copy cites handoff `504ca113`, but **§8 auditor handoff is not contained in that commit** → `artifact-not-in-HEAD` (F-001).

---

## 3. Context chain completeness

| Artifact | Status | Limits |
|----------|--------|--------|
| Context map | Provided | Stale vs landed code; still valid for scope/coupling |
| Plan + packets T1/T2 | Provided | §8 incomplete in git |
| Decision log T1 | Provided | — |
| Superseded tail log T2 | Provided | Supersession banner verified |
| CHANGELOG | Provided | — |
| Code (anchor + HEAD) | Provided | HEAD adds unrelated `pacing-before-llm` only |
| Tests | Provided + executed | No Silero integration tests (by design) |
| Pre-plan / roadmap notes | Not separately provided | Context map sufficient |

---

## 4. Cold-read log (Phase 0 — pinned)

| ID | Severity (guess) | Finding |
|----|------------------|---------|
| CR-1 | observation | `play_gate_frame_tick` + loop integration present; emit guard retained at `_emit_audio_segment` |
| CR-2 | observation | Per-frame `continue` when `is_playing` after tick — drained PCM not fed to `vad_iter` while gated |
| CR-3 | minor | No pytest drives `_capture_loop` with toggling `is_playing` (only pure helper + emit tests) |
| CR-4 | observation | Max-speech branch has inline discard when `is_playing` (defense-in-depth; normal path `continue`s first) |
| CR-5 | minor | Two `self._is_playing.is_set()` calls per frame (tick vs `continue`) — narrow cross-thread clear race on gate edge (see adversarial A-3) |

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| F-001 | major | artifact-not-in-HEAD | 0.5 | T2 / closure | `plan.md` §8 auditor handoff and `Status: Complete` exist only in **uncommitted** working tree; `504ca113` and `HEAD` end §8 with **"Not produced"** |
| F-002 | major | context-map-stale | 0.5 | scout | Scout SHA `e3fd9dc` diverges from anchor on all direct/touched files (expected post-execution) |
| F-003 | minor | coverage-gap | 5 | T1 | No automated test for max-speech discard branch while `is_playing` (deferred in T1 decision log) |
| F-004 | minor | coverage-gap | 5 | T2 | No pytest sync for `heckler_seed.md` / `README.md` mic-gate prose (explicitly deferred in CHANGELOG) |
| F-005 | observation | coverage-gap | 5 | T1 | No integration test for `_capture_loop` + Silero under play gate (plan non-goal / kill criterion 3) |
| F-006 | observation | adversarial-fail | 4 | T1 | Theoretical one-frame stale `vad_iter` if `is_playing` clears between tick and `continue` (single-threaded frame loop vs other-thread `Event.clear`) |

No `intent-drift`, `contract-violation`, `narrative-concealment`, or `process-violation` (executor HALT) findings on **shipped code** at anchor SHA.

---

## 6. Detailed findings (above minor)

### F-001 — `artifact-not-in-HEAD` (major)

**Expected:** Orchestrator §8 closure at handoff SHA `504ca113` includes completion snapshot, artifact chain, and `Status: Complete` in tracked `plan.md`.

**Found:** `git show 504ca113:.dev/plans/capture-mic-gate-during-play/plan.md` and `git show HEAD:.../plan.md` both terminate §8 with:

> **Not produced** — populate when execution marks plan *Complete*

Working-tree `plan.md` (unstaged) contains full §8.1–§8.6 and `Status: Complete (v1.0 — §8 auditor handoff populated 2026-05-22)`.

**Evidence:** `git diff HEAD -- .dev/plans/capture-mic-gate-during-play/plan.md` shows +87 lines for §8; T2 commit `504ca113` stat lists `plan.md` (+168 lines) but not post-T2 §8 append.

**Impact:** Post-merge audit archaeology breaks — auditors cannot rely on `git show <handoff>:plan.md` for §8 evidence table without this commit.

**Action:** Commit working-tree `plan.md` (or amend T2 only if unpushed and user requests amend) so §8 and status match landed work.

---

### F-002 — `context-map-stale` (major, process)

**Expected:** Context map provenance matches code reviewed for scout-flagged symbols.

**Found:** Scout at `e3fd9dc`; implementation landed `da8aca82` / `504ca113`. Interface inventory rows for `_capture_loop` / `_emit_audio_segment` describe **pre-T1** behavior (lines 148–184 emit-only gate).

**Impact:** Findings tied to scout line numbers are stale-qualified; implementation review used anchor `504ca113` / current files.

**Action:** No code change; optional scout refresh if another plan touches capture.

---

## 7. Adversarial test log (Phase 4)

**Focus rationale:** Mandatory integration seams from §Coupling surfaces; concurrency on shared `Event` clear edge.

| ID | Scenario | Expected | Actual | Result |
|----|----------|----------|--------|--------|
| A-1 | Shared `Speaker.is_playing` → capture while set (Surface 1) | No VAD segment formation; no enqueue | `play_gate_frame_tick` clears state; `continue` before `vad_iter`; emit guard at 116–117 | **pass** |
| A-2 | PCM deque fills while gated (Surface 5) | Drained frames dropped, not accumulated | `_drain_pcm_batch` each iteration; gated frames `continue` without `vad_iter` | **pass** |
| A-3 | Gate clears between `tick()` and `continue` `is_set()` (concurrency) | First open frame resets VAD before processing | If clear between calls: one frame may run `vad_iter` before `was_gated` clear edge on **next** frame sets `reset_vad` | **unknown** (narrow window; mitigated next frame) |
| A-4 | VADIterator stale after unmute (Surface 3) | Rebuild on first open frame after gated period | `was_gated` + not playing → `reset_vad=True` → `new_vad_iterator()` | **pass** (helper test + code 207–208) |
| A-5 | Max-speech flush during play (Surface 6) | No `_emit_audio_segment` | Branch 215–219 discards; normal path unreachable while gated due to 205–206 | **pass** |
| A-6 | Transcribe never-set `Event` (Surface 4) | Always open | No `controller.py` diff in T1/T2 | **pass** |
| A-7 | Emit-time second defense (Surface 7) | Retained | `test_emit_skips_when_speaker_is_playing` + code | **pass** |
| A-8 | Barge-in during tail (Surface 2) | Blocked by shared Event | Documented tradeoff in T1 decision log; no code change | **pass** (by design) |

---

## 8. Coverage gap list (prioritized)

| Priority | Gap | Kill criterion? | Mitigation |
|----------|-----|-----------------|------------|
| P2 | Max-speech + `is_playing` branch | T1 KC (6) — logic present, not pytest-falsified | Decision log deferred; per-frame `continue` is primary defense |
| P3 | `_capture_loop` under real Silero/hardware | No (explicit non-goal) | Manual persona run |
| P3 | Markdown prose ↔ helper semantics | No | CHANGELOG + audit discipline |
| P4 | Gate-clear race (A-3) | No | Theoretical; helper tests cover state machine |

No `process-violation` for kill-criterion vs coverage contradiction — deferrals are written in T1 log and CHANGELOG.

---

## 9. Phase 1–3 summary (post-narrative)

**Intent traceability:** Task §1 Rule 1 (no VAD during play, discard partial segment, reset VAD on clear, complement emit guard) matches `da8aca82` / current `audio_capture.py`. Non-goals respected: no `Speaker`/`controller`/`pacing_gate` changes in plan commits; `pacing-before-llm` at HEAD is separate.

**Map → plan → packets → diff:**

| Subtask | Packet files | Landed (`504ca113` ancestry) | Notes |
|---------|--------------|------------------------------|-------|
| T1 | `audio_capture.py`, `test_audio_capture.py`, T1 decision log | `da8aca82` exact match | +3 helper tests |
| T2 | seed, CHANGELOG, README, tail log, plan bundle | `504ca113` | `plan.md` §8 incomplete in git (F-001) |

**Contract compliance (§2):**

- `PlayGateFrameResult` / `play_gate_frame_tick` — names, fields, semantics match §2; three unit tests round-trip.
- `_capture_loop` — `_play_gate_was_gated`, per-frame tick, `continue` when playing, `reset_vad` path OK.
- `_emit_audio_segment` guard retained.
- Error envelope tests unchanged.
- No new CLI/config surfaces.

**Decision log T1:** Chosen approach implemented; deferred items for docs/supersession marked landed in T2 in log body; max-speech integration test still deferred with rationale — consistent with code.

**Supersession:** `tts-mic-gate-tail-T2.md` §Superseded assumption present; tail behavior remains complementary.

**Cold-read reconciliation:** No `narrative-concealment` — orchestrator review and §8 working copy acknowledge test/deferral gaps; git §8 absence is F-001 not concealment of code defects.

---

## 10. Scout-prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| Surface 1 — shared Event buffer-then-emit | confirmed coupling | **verified** | Loop + emit guard |
| Surface 2 — gate window barge-in | confirmed | **verified** | Documented tradeoff |
| Surface 3 — VADIterator reset on unmute | confirmed | **verified** | `reset_vad` + test |
| Surface 4 — persona vs transcribe wiring | confirmed | **verified** | No controller diff |
| Surface 5 — PCM deque backlog | confirmed | **verified** | Drain + drop while gated |
| Surface 6 — max-speech flush during play | suspected | **ruled out** (implementation guards) | A-5 |
| Surface 7 — emit second defense | confirmed | **verified** | Guard + test |
| Flag 1 — loop placement | ambiguity | **verified** | Per-frame tick + continue |
| Flag 2 — discard whole segment | ambiguity | **verified** | `play_gate_frame_tick` clears segment |
| Flag 3 — CI without hub | ambiguity | **verified** | Pure helper tests only |
| Flag 4 — keep emit check | ambiguity | **verified** | Retained |
| Flag 5 — pacing ship order | ambiguity | **verified** | No pacing edits in plan commits |
| `_capture_loop` suspect_modified | inventory | **verified** | Landed T1 |
| `_emit_audio_segment` suspect_modified | inventory | **verified** | Guard retained |
| `play_gate_frame_tick` (not in scout inventory) | — | **not-tested** (planner-introduced) | Present in code — expected |

---

## 11. Verdict

**`pass-with-conditions`**

**Implementation (anchor `504ca113` and current HEAD capture files):** Contracts and intent are satisfied; pytest green; integration seams closed per plan. Safe to treat capture-layer Rule 1 as **landed**.

**Conditions before considering the plan bundle audit-complete:**

1. **F-001:** Commit `plan.md` §8 and `Status: Complete` so handoff SHA (or a documented follow-up commit) contains the §8 artifact chain the working tree already describes.
2. Acknowledge **F-002** staleness if reusing this context map without refresh.

**Would upgrade to `fail` if:** merge policy requires §8-in-HEAD for any `.dev/plans/*` closure — then F-001 alone blocks archive completeness (major `artifact-not-in-HEAD`).

**Would upgrade to `pass` after:** F-001 resolved with no new major/critical findings on re-audit of `plan.md` only.
