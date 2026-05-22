# Audit — tts-mic-gate-tail

**Audit document revision:** 1 (initial)  
**Date:** 2026-05-21  
**Plan:** `tts-mic-gate-tail` v1.0  
**Auditor focus areas:** Integration seams (§Coupling surfaces), failure paths (`try`/`finally` + error-path tests), typed-config admission (`TTS_GATE_TAIL_MS` three-leg check)  
**Context map:** `.dev/plans/tts-mic-gate-tail/context-map.md` — readiness **CONDITIONAL** at planning time  
**Audit HEAD:** `3cfc2052c26928764cbbf674be78d593bbccee7d` (matches plan §8.1 Tree SHA)  
**Working tree at audit:** `M .dev/plans/tts-mic-gate-tail/plan.md` (§8 handoff populated locally, not in `HEAD`)

---

## 1. Audit metadata

| Field | Value |
|-------|--------|
| Task | Post-playback acoustic tail on `Speaker.is_playing` (`tts_gate_tail_ms` / `TTS_GATE_TAIL_MS`) |
| Plan version | 1.0, status *Complete* (working tree); *Planning complete — execution pending* (`HEAD` `plan.md`) |
| Scout SHA | `58f10f132078691a70cc0ae70a5304816fce1f25` |
| Implementation chain | `abbaa65f` (T1) → `25718245` (T2) → `3cfc2052` (T3) |
| Phase 0 discipline | Completed before reading context-map body (beyond provenance header), packets, decision log, or CHANGELOG |
| `pytest tests/test_config.py tests/test_speaker.py -q` | **29 passed**, 2.28s (auditor re-run 2026-05-21) |

---

## 2. Provenance log (Phase 0.5)

| Check | Result |
|-------|--------|
| Context map path | `.dev/plans/tts-mic-gate-tail/context-map.md` — present |
| Scout readiness | CONDITIONAL (tail configurable vs constant — resolved in plan §0) |
| SHA comparison | **diverged** — scout `58f10f1` vs audit HEAD `3cfc2052` |
| Diverged §File map `direct` rows | `heckler/speaker.py`, `heckler/config.py`, `tests/test_speaker.py` (expected post-implementation) |
| Diverged §File map `adjacent` rows (implementation touch) | `heckler_seed.md`, `CHANGELOG.MD`, `README.md`, `.env.example` |
| Scout working tree at scout time | **dirty** — `next_steps.md` (out of scope); no in-scope dirty paths at scout time |
| Scout grep coverage vs plan §5.4 | **complete** — `is_playing`, `record_output`, `_execute_spoken_reply`, `HecklerConfig`/`load_config`, `24000`/`blocking=True`, doc coupling patterns all recorded |
| Plan-artifact provenance @ `HEAD` | context-map, plan (stale §8), packets T1–T3, decision log T2, CHANGELOG section — **present-in-HEAD** |
| Plan §8 populated handoff | **on-disk-only** — working-tree `plan.md` differs from `git show HEAD:.../plan.md` |
| Closure SHA verification | §8.1 cites `3cfc2052` — matches `git rev-parse HEAD`; artifacts listed in §8.2 exist at that SHA except §8 body itself |

**Findings filed in Phase 0.5**

| ID | Severity | Type | Summary |
|----|----------|------|---------|
| FIND-01 | major | `context-map-stale` | Scout SHA predates T1–T3; line-level `speaker.py`/`config.py` inventory is stale-qualified |
| FIND-02 | major | `artifact-not-in-HEAD` | Populated plan §8 (completion snapshot, §8.2–§8.5) exists on disk but not in `HEAD` |
| FIND-03 | major | `process-violation` | Working-tree `plan.md` §8.1 claims clean tree; auditor sees unstaged §8 edits |

---

## 3. Context chain completeness

| Artifact | Provided | Notes |
|----------|----------|-------|
| Context map | Yes | Stale vs implementation; roles/flags still valid |
| Plan §1–§2 (Phase 0) | Yes | Task statement + shared contracts consumed before narrative |
| Plan §0–§8 full | Yes | §8 reconciled against `HEAD` vs working tree in FIND-02/03 |
| Packets T1–T3 | Yes | |
| Decision log T2 | Yes | Architectural tier |
| CHANGELOG | Yes | `tts-mic-gate-tail` section |
| Code + tests | Yes | Cold-read + contract verification |
| Prior audit | No | Initial audit |
| Pre-plan unstructured notes | No | Context map + `logs/heckler_2026-05-09.jsonl` cited in plan suffice |

**Limits:** Stale-qualified findings on scout line numbers for `speaker.py`/`config.py`. Echo suppression on real hardware remains operator validation (plan §8.4 assumption 3).

---

## 4. Cold-read log (Phase 0 — pinned)

| ID | Severity (guess) | File / surface | Finding |
|----|------------------|----------------|---------|
| CR-01 | — (pass) | `heckler/speaker.py` | Tail `sleep` sits after successful `sd.play` inside playback `try`; `finally` always clears |
| CR-02 | — (pass) | `heckler/speaker.py` | Synthesis `except` clears before playback block; play failure cannot reach `sleep` body |
| CR-03 | — (pass) | `tests/test_speaker.py` | Default fixture `tts_gate_tail_ms=0` isolates legacy immediate-clear tests |
| CR-04 | minor? | `heckler_seed.md` (later) | Pseudo-docstring claims `sd.play` exception re-raised as `SpeakerError` — code propagates original exception |
| CR-05 | major? | `plan.md` vs `HEAD` | §8 completion block present on disk only; conflicts with “clean tree” claim |

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | One-line description |
|----|----------|------|-------|---------|----------------------|
| FIND-01 | major | `context-map-stale` | 0.5 | — | Scout @ `58f10f1`; implementation @ `3cfc2052` on direct map files |
| FIND-02 | major | `artifact-not-in-HEAD` | 0.5 | T3 | Populated plan §8 auditor handoff not committed to `HEAD` |
| FIND-03 | major | `process-violation` | 0.5 / 1 | T3 | §8.1 “clean tree” false while `plan.md` modified |
| FIND-04 | minor | `contract-violation` | 1 / 2 | T3 | `heckler_seed.md` play-failure prose says `SpeakerError`; §2/code propagate `sd.play` errors |
| FIND-05 | minor | `coverage-gap` | 5 | T3 | No automated doc↔default sync (explicitly deferred in CHANGELOG) |
| FIND-06 | observation | — | 3 / 5 | T1 | Negative/large `TTS_GATE_TAIL_MS` unvalidated (deferred in T2 decision log) |
| FIND-07 | observation | `undeclared-change` | 1 | T3 | `next_steps.md` deletion in T3 commit outside packet files-to-touch |
| FIND-08 | observation | — | 4 | — | 400 ms default echo suppression is hardware-dependent (plan “treat-as-prediction”) |

---

## 6. Detailed findings (above minor)

### FIND-01 — `context-map-stale` (major)

**Expected:** Context map provenance matches implementation HEAD for §File map `direct` rows.  
**Found:** Scout recorded `Speaker.speak` lifecycle through line ~70 with immediate `finally: clear()` after `sd.play`. Implementation adds tail sleep and extended tests.  
**Evidence:** Scout SHA `58f10f1` in `context-map.md` header; `git diff 58f10f13..3cfc2052` touches `heckler/speaker.py`, `heckler/config.py`, `tests/test_speaker.py`. Plan §0 documents staleness.  
**Action:** Re-scout optional; does not invalidate code audit. Findings on stale line refs are stale-qualified.

### FIND-02 — `artifact-not-in-HEAD` (major)

**Expected:** Plan §8 auditor handoff committed at T3 closure SHA.  
**Found:** `git show HEAD:.dev/plans/tts-mic-gate-tail/plan.md` ends with “**Not produced** — populate when execution marks plan *Complete*”. Working tree adds §8.1–§8.5 (status *Complete*, tree SHA, evidence table).  
**Evidence:** `git diff HEAD -- .dev/plans/tts-mic-gate-tail/plan.md` (~75 lines).  
**Action:** Commit populated `plan.md` (or amend T3) so post-merge `git show` resolves §8.2 read order.

### FIND-03 — `process-violation` (major)

**Expected:** §8.1 “Working tree at verification: Clean” when claiming completion.  
**Found:** `git status` shows `M .dev/plans/tts-mic-gate-tail/plan.md` at audit time.  
**Evidence:** Uncommitted §8 block (FIND-02).  
**Action:** Commit `plan.md` with §8; re-run handoff verification on clean tree.

### FIND-04 — `contract-violation` (minor)

**Expected:** §2 error envelope: `SpeakerError` on synthesis; `sd.play` exceptions propagate after `clear()`.  
**Found:** `heckler_seed.md` embedded `speak` doc (L588) says synthesis **or sd.play** exception “re-raise as `SpeakerError`”. `Speaker.speak` only wraps synthesis failures; `test_play_failure_still_clears_event` expects `OSError`.  
**Evidence:** `heckler/speaker.py` play `try` has no `except` wrapping; T3 seed edit introduced combined wording (pre-T3 seed had synthesis-only `SpeakerError`).  
**Action:** Split seed prose: synthesis → `SpeakerError`; play → propagate after clear.

---

## 7. Adversarial test log (Phase 4)

### Focus A — Integration seams (required; seeded from §Coupling surfaces)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Surface 1 — shared `Event` suppresses capture while gate set | `AudioCapture._emit_audio_segment` returns when `is_playing.is_set()` | Unchanged; `test_emit_skips_when_speaker_is_playing` | **pass** |
| Surface 1 — tail extends hold | Gate set during mocked post-play sleep | `test_speak_holds_mic_gate_during_post_playback_tail` asserts `gate_during_tail == [True]` | **pass** |
| Surface 2 — pacing order frozen | `record_output()` immediately before `speak()` | `pipeline._execute_spoken_reply` L46–47 unchanged in T1–T3 commits | **pass** |
| Surface 3 — transcribe mode | Bare `threading.Event()` never set | No `controller.py` diff in plan commits | **pass** |
| Surface 4 — 24 kHz blocking play | `samplerate=24000`, `blocking=True` | Unchanged; existing speaker tests | **pass** |
| Surface 5 — seed/doc coupling | Seed + README + `.env.example` describe tail | Updated at T3; play-error wording drift (FIND-04) | **pass** with doc caveat |
| Surface 6 — user overlap during tail | Longer hold may discard overlapping user audio | By design; default 400 ms + env tunable; no automated UX test | **unknown** (manual) |
| §5.4 suspected — monkeypatched sleep vs wall clock | Assert gate during fake sleep, not real time | `test_speak_holds_mic_gate_during_post_playback_tail` | **pass** (ruled out) |

### Focus B — Failure paths

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Synthesis failure | Clear without tail; `SpeakerError` | `except` clears before play; `test_synthesis_failure_skips_post_playback_tail_sleep` | **pass** |
| `sd.play` failure | Clear without tail; exception propagates | Sleep body skipped; `test_play_failure_skips_post_playback_tail_sleep` + `test_play_failure_still_clears_event` | **pass** |
| Invalid `TTS_GATE_TAIL_MS` | Startup `ValueError` | `test_load_config_tts_gate_tail_ms_invalid_raises` | **pass** |
| `tts_gate_tail_ms=0` | No sleep; immediate clear after play | Fixture + dedicated tests | **pass** |

### Focus C — Typed-config admission (§2 three-leg)

| Leg | Expected | Actual | Result |
|-----|----------|--------|--------|
| (a) Dataclass field | `tts_gate_tail_ms: int = 400` | `heckler/config.py` L34 | **pass** |
| (b) `load_config()` admits env | `int(os.getenv("TTS_GATE_TAIL_MS", "400"))` | L76; not dropped | **pass** |
| (c) Round-trip tests | default, override, zero, invalid | Four tests in `tests/test_config.py` | **pass** |
| Runtime read in Speaker | `self._config.tts_gate_tail_ms` | No hardcoded ms in `speaker.py` | **pass** |

---

## 8. Coverage gap list (Phase 5)

| Priority | Gap | Severity | Notes |
|----------|-----|----------|-------|
| 1 | Doc/default sync (README, seed, `.env.example`) | minor | Deferred in CHANGELOG T3; FIND-05 |
| 2 | Echo suppression on physical hardware | observation | Plan assumption 3; env tunable |
| 3 | User barge-in during tail window | observation | Coupling surface 6; UX tradeoff documented |
| 4 | Negative / huge `TTS_GATE_TAIL_MS` | observation | Deferred in decision log |
| 5 | Play failure with non-zero tail configured | — | Covered implicitly: exception skips sleep; could add explicit `tts_gate_tail_ms=400` test for clarity (optional) |

Kill criteria from packets: all observable criteria have matching tests except doc-sync (waived in writing) and hardware echo (manual).

---

## 9. Intent traceability (Phase 1 summary)

| Layer | Verdict |
|-------|---------|
| Task statement → plan §1 | Aligned — post-playback tail in `Speaker.speak`, non-goals respected |
| Plan §4 files → actual diff | T1/T2 match packets; T3 adds `next_steps.md` (FIND-07); plan bundle tracked |
| §2 contracts → code | **Honored** on runtime surfaces (FIND-04 doc-only) |
| Context map flags → resolution | Flags 1–4 resolved per plan §0; Flag 3 test added in T2 |
| Non-goals | No `AudioCapture`/`pipeline`/`pacing_gate`/CLI/GUI/reactor dedup changes |
| Cold-read vs narrative | CR-04/05 acknowledged in FIND-04/02/03 — no `narrative-concealment` |
| Prior reasoning (T8/T9) | Supersession explicit in plan §0, decision log, seed Coupling Surface 2 |

---

## 10. Decision log audit (Phase 3)

**`.dev/decision-logs/tts-mic-gate-tail-T2.md`**

| Check | Result |
|-------|--------|
| Chosen approach implemented | Tail after successful `sd.play`, `finally` clear — matches code |
| Rejected alternatives avoided | No tail in `finally` after clear; no capture/reactor dedup; latency excludes tail |
| Assumptions | AudioCapture `is_set()` contract holds — tested indirectly |
| Deferred items | Negative/large env values not validated — still deferred, not silently implemented |
| Stale prose | No unfenced pre-amendment behavior claims contradicting code |

T1 standard tier — no decision log required. Correct.

---

## 11. Scout-prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| Surface 1 — shared Event mic gate | confirmed coupling | **verified** | — |
| Surface 2 — pacing `record_output` before speak | confirmed | **verified** | — |
| Surface 3 — persona vs transcribe `is_playing` | confirmed | **verified** | — |
| Surface 4 — 24 kHz play rate | confirmed | **verified** | — |
| Surface 5 — seed/doc wording drift | suspected | **verified** (docs updated; minor play-error drift FIND-04) | FIND-04 |
| Surface 6 — user speech during tail | confirmed | **not-tested** (manual) | — |
| Flag 1 — configurable vs constant tail | ambiguity | **verified** | `tts_gate_tail_ms` + env |
| Flag 2 — tail only on successful play | ambiguity | **verified** | error-path tests |
| Flag 3 — missing post-play hold test | ambiguity | **verified** | `test_speak_holds_mic_gate_during_post_playback_tail` |
| Flag 4 — default ms tradeoff | ambiguity | **verified** (400 default shipped) | FIND-08 observation |
| `Speaker.speak` suspect_modified | inventory | **verified** | — |
| `HecklerConfig`/`load_config` suspect_modified | inventory | **verified** | — |
| §5.4 test immediate-clear coupling | hidden | **verified** | fixture `tts_gate_tail_ms=0` |
| §5.4 monkeypatch vs wall clock | suspected | **ruled-out** | adversarial pass |

---

## 12. Verdict

**`pass-with-conditions`**

Runtime implementation matches intent and §2 contracts. Tests pass. No critical or major **code** defects.

**Conditions before merge (process / archive):**

1. **Commit** working-tree `.dev/plans/tts-mic-gate-tail/plan.md` with populated §8 so `artifact-not-in-HEAD` (FIND-02) and false clean-tree claim (FIND-03) close.
2. **Recommended (minor):** Fix `heckler_seed.md` L588 play-exception wording to match §2 error envelope (FIND-04).

**Does not block merge (acceptable with justification):**

- FIND-01 context-map staleness (documented; re-scout optional).
- FIND-05 doc-sync pytest gap (explicitly deferred).
- FIND-06/07/08 observations.

---

## 13. Phase 2 contract checklist (abbreviated)

| §2 row | Status |
|--------|--------|
| `tts_gate_tail_ms` / `TTS_GATE_TAIL_MS` | OK |
| Tail in `Speaker.speak` after successful play | OK |
| Error paths no tail | OK |
| `tts_latency_ms` synthesis-only | OK |
| `AudioCapture` unchanged | OK |
| Naming literals | OK (`TTS_GATE_TAIL_MS` in README, `.env.example`) |
| Logging | N/A |
| CLI | N/A |
| Tests | 29 passed |
