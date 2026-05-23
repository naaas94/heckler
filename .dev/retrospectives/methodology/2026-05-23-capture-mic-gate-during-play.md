# Retrospective — methodology · capture-mic-gate-during-play

**Date:** 2026-05-23  
**Plan:** `.dev/plans/capture-mic-gate-during-play/plan.md` **v1.0** (orchestrator-planning **v0.6**; no §7 amendments)  
**Context map:** pre-plan-exploration **v0.2** @ scout `e3fd9dc5c58278f46e3d5729f214927db5dd3dcd`  
**Audits:** `.dev/audits/2026-05-22-capture-mic-gate-during-play.md` (rev **1** only) → **`pass-with-conditions`** (F-001, F-002)  
**Commits (landed):** T1 `da8aca82` · T2 `504ca113` · §8 + audit index `bb7746aa` · current `HEAD` `adcbec9b` (capture paths unchanged since `504ca113`)  
**One line:** Capture-layer **Rule 1** while `Speaker.is_playing` — `play_gate_frame_tick` + `_capture_loop` discard/reset, emit guard retained, docs supersession — fixing buffer-then-emit echo after the shipped tail-only plan.

**Artifacts read:** `plan.md` (§0–§8, execution review), `context-map.md`, packets T1/T2, `capture-mic-gate-during-play-T1.md`, `tts-mic-gate-tail-T2.md` (supersession), `CHANGELOG.MD`, audit rev 1, `heckler/audio_capture.py`, `tests/test_audio_capture.py`, `heckler_seed.md` (mic-gate rows), `git log` / `git show` for `da8aca82`, `504ca113`, `bb7746aa`, `HEAD`.

---

## 1. Task identifier

- **Name:** capture-mic-gate-during-play  
- **Planning / execution dates:** context map 2026-05-21; plan + land 2026-05-22; audit 2026-05-22; §8 commit bundled 2026-05-22 (`bb7746aa`)  
- **What it was:** Stop Silero VAD from forming segments while TTS/playback/tail holds `is_playing`, discard partial capture, reset `VADIterator` on unmute, keep `_emit_audio_segment` skip — complementing `tts-mic-gate-tail` without touching `Speaker`, `controller`, or `pacing_gate`.

---

## 2. Plan vs reality

### DAG vs execution

**Matched.** Strict `T1 → T2`, no parallel groups. `pacing-before-llm` landed on the same branch **after** T2 (`0da7ac52`, `692dfa0c`, …) but did not touch `audio_capture.py` or `test_audio_capture.py` (audit confirmed anchor→HEAD **match** on capture files). Interleaved history is noisy for archaeology, not unsafe for this plan’s file ownership.

### Contracts at the implementation surface (§2)

| §2 surface | Enforced in code + test? | Notes |
|------------|--------------------------|-------|
| `PlayGateFrameResult` / `play_gate_frame_tick` | **Yes** — three pure-helper tests | No Silero hub in pytest (Flag 3 satisfied) |
| `_capture_loop` tick, `continue` while playing, `reset_vad` | **Code yes; loop pytest no** | By explicit non-goal / kill criterion 3; state machine covered by helper |
| `_emit_audio_segment` guard | **Yes** — `test_emit_skips_when_speaker_is_playing` | Second defense retained |
| `Speaker` / `controller` unchanged | **Yes** — no diffs in T1/T2 on those files | |
| Error envelope | **Yes** — existing reject tests unchanged | |
| Max-speech flush while `is_playing` | **Logic yes; pytest no** | KC (6) satisfied in code (`215–219`); deferred in T1 log (F-003) |
| CLI / logging | N/A | |

**Hollow-contract assessment:** Not a “green tests, missing symbols” failure. The deliberate hollow is **integration depth**: helper tests prove the state machine; **no** falsifier drives `_capture_loop` with toggling `Event` or Silero. That matches plan non-goals and audit F-003/F-005 — deferrals are written, not papered over. Risk: loop wiring could drift from `play_gate_frame_tick` without pytest catching it.

### §2 / decision-log narrative survival

- **Pre-plan → plan:** All five context-map flags resolved in plan §0 before packets — good; executors did not need mid-flight Flag HALTs.
- **T1 decision log → T2:** Deferred prose/supersession items marked **Landed in T2** in the same commit that edited the log (`504ca113`) — repaired in-session.
- **Context map:** Still describes **pre-T1** `_capture_loop` (emit-only gate, lines 148–184). Audit **F-002** (`context-map-stale`) — valid; map remains usable for coupling surfaces, wrong for line-accurate inventory.
- **Plan §8.2 row for `plan.md`:** Honestly notes “§8 appended post-T2 on working tree” while artifact table still says `git show 504ca113` **OK** for plan — **internally inconsistent** until reader notices handoff SHA vs §8 body mismatch.

### Log tiers

- **T1 `architectural`:** Appropriate — new typed surface, loop semantics, supersession of tail-plan assumption.
- **T2 `standard`:** Appropriate — docs + git-tracking plan bundle.

Nothing clearly mis-tiered.

### Closure vs committed reality

**Leak (same family as transcription-engine / persona-system / pacing-before-llm).**

| Checkpoint | What §8 / status claimed | What `git show` proved |
|------------|-------------------------|-------------------------|
| After **T2** `504ca113` | Plan bundle “tracked for §8.2” | `plan.md` ends §8 with **“Not produced”**; no `Status: Complete` |
| At **audit** (`HEAD` `0da7ac52`) | Working tree: full §8 + Complete | `HEAD:plan.md` still **“Not produced”** → **F-001** |
| After **`bb7746aa`** | §8 + Complete in git | **Fixed** for `git show bb7746aa:plan.md` |
| **Current** `HEAD` | §8 present | Handoff table still cites **`504ca113`** as “T2 commit; includes T1” for verification — **that SHA does not contain §8** |

So: F-001 is **remediated in git** (`bb7746aa`), but **closure narrative is still wrong** for strict `git show <handoff>:plan.md` archaeology. No follow-up commit updated handoff SHA to `bb7746aa` or added a “§8 introducer” row (contrast transcription-engine’s explicit `026d68d` bundle introducer after T6).

**Audit vs tree:** First audit ran with **dirty** working tree (§8 unstaged). Audit correctly filed F-001; implementation review used anchor **`504ca113`** for code — correct discipline. **No audit rev 2** after `bb7746aa` despite audit text “upgrade to pass after F-001 resolved.”

**pytest:** `11 passed` at audit HEAD; **11 passed** on 2026-05-23 re-run — stable.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Zero** in-repo (no HALT transcripts, packets, or decision-log escalations). Context-map **CONDITIONAL** flags were all resolved in plan §0 before T1 — kill criteria functioned as **pre-negotiated** constraints, not runtime stops.

**False HALT risk:** Low — scope stayed inside `audio_capture.py` + tests + docs; no `Speaker`/`pacing_gate` creep.

### HALT-shaped silent improvisation

**Yes — closure-shaped, not code-shaped.**

- T2 commit message and CHANGELOG describe a **complete** doc/plan bundle, but **§8 auditor handoff was left as stub** in the same commit that added `plan.md` (+168 lines).
- Orchestrator **“Execution review (pre-audit)”** and full §8.1–§8.6 existed on disk (and in audit working tree) while git still said **Not produced** — “complete” narrative **ahead of** indexed artifacts. Same failure mode as transcription-engine **v1.0 §8**, but **without** a formal **§7 amendment** (e.g. T6-shaped) to close it.
- **`bb7746aa`** fixed §8 in one megacommit that also: tracked audit files, archived other plans, appended **pacing-before-llm** §8, added transcripts. F-001 remediation was **not** scoped as an amendment subtask; provenance is harder to read than a single-purpose closure commit.

### Amendment cycles

**Plan §7:** None declared; none executed.

**Audit-driven remediation:** F-001 addressed outside §7 → **process gap** vs transcription-engine (which used **T6** + audit rev **2** `pass`). Here: condition met in git, **audit document frozen** at `pass-with-conditions` with F-001 still listed as open.

---

## 4. Adversarial pass calibration

### Rejected decompositions (§5.1)

**Held up.**

1. **Speaker-only / longer tail** — Correctly rejected; tail plan already shipped; validated failure mode is **buffer-then-emit** in `_capture_loop`, not tail length alone (`tts-mic-gate-tail-T2` assumption superseded).
2. **Emit-only** — Correctly rejected; pre-change code already had emit skip; echo persisted.
3. **Split tests to T3** — Correctly rejected for a 2-node DAG; tests are falsifiers for the helper contract.

### Load-bearing assumptions (§5.2)

Audit §8.4 / adversarial log — **all closed** at anchor `504ca113`:

- Shared `Event` wiring — unchanged `controller.py`.
- Discard PCM while gated — drain + `continue` before `vad_iter`.
- `reset_vad` on clear edge — helper test + loop assignment.
- Emit second defense — retained + test.
- `tts_gate_tail_ms` — treat-as-prediction (pre-existing); not modified.

### Highest re-plan risk (§5.3)

**T1 — Silero `VADIterator` after reset / max-speech interaction:** Did **not** trigger re-plan or amendment. Audit A-4/A-5 **pass** on code; F-006 notes a **narrow theoretical** clear-edge race (two `is_set()` calls per frame) — **unknown**, mitigated next frame; not escalated.

**Trouble came from elsewhere:** **Planning closure** (§8-in-HEAD, handoff SHA honesty), not VAD integration. Same pattern as §5.3’s “T6 process risk” on other plans, but this plan had **no T6** — only bundled `bb7746aa`.

### Hidden couplings (§5.4)

| Coupling | Outcome |
|----------|---------|
| Emit-only test gap | **Closed** — 3× `test_play_gate_frame_tick_*` |
| Silero hub in CI | **Closed** — no new hub tests |
| Max-speech during play | **Closed in code**; pytest gap **deferred** (F-003) |
| Transcribe never-set `Event` | **Closed** — no controller diff |
| `heckler_seed.md` misleading prose | **Closed** — T2 seed §4.1 / §4.7 / Surface 2 |
| Pacing-before-llm conflation | **Closed** — T2 kill (1); separate plan landed later |

Scout inventory did not list `play_gate_frame_tick` (planner-introduced) — audit marks **not-tested** at scout level; expected.

---

## 5. Methodology gaps surfaced

### Orchestrator / §8 discipline (recurring)

- **Do not** set `Status: Complete` or populate §8.1–§8.6 until `git show <cited-sha>:.dev/plans/.../plan.md` contains that body (transcription-engine retro already flagged this; **repeated here**).
- **Handoff SHA** should be either (a) the commit that **first** contains full §8, or (b) dual-SHA table: `implementation_sha` vs `closure_sha`. Citing `504ca113` while §8 lives in `bb7746aa` breaks `§8.2` “`git show 504ca113:<path>`” for the plan row.
- **Execution review (pre-audit)** in `plan.md` is valuable but dangerous if committed while §8 stub remains — reads as auditor-ready when merge archaeology is not.

### Executor

- T2 scope included “commit plan bundle” — landed `plan.md` **without** §8 body. Executor skill implication: “tracked plan bundle” should include **orchestrator §8 completion** when plan status is Complete, or explicitly leave status **In progress** until §8 commit.
- **nothing notable** on contract bypass in shipped code (audit: no intent-drift / contract-violation on anchor).

### Auditor / amendment pairing

- **F-001 fix without rev 2 audit** leaves a permanent `pass-with-conditions` record that understates final state.
- Megacommit **`bb7746aa`** mixes capture §8, pacing §8, audit files, archive moves, transcripts — works for velocity, weak for **per-plan** closure attribution (contrast formal **T7** on persona-system or **T6** on transcription-engine).

### Contracts schema

- **nothing notable** — §2 rows were adequate; gap was **test depth choice** (helper-only), explicitly documented, not schema missing fields.
- Optional future row: **`closure_sha`** distinct from **`implementation_sha`** when §8 is appended post-implementation commit.

*(Per skill: do not edit orchestrator/executor/auditor skills from this file.)*

---

## 6. Single sentence verdict

**Partially** — the DAG, §2 typed surface, kill-criteria-aligned implementation, and adversarial §5 disposition **held** on code at `504ca113`, but **§8 completion leaked** (F-001) until a **non-amendment** bundled commit, **without re-audit** and with a **residual handoff-SHA vs §8-location mismatch**, so the methodology **did not fully hold** on first closure even though runtime Rule 1 is landed and pytest-green.
