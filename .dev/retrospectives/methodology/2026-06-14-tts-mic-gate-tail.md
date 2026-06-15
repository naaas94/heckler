# Retrospective — methodology · tts-mic-gate-tail

**Date:** 2026-06-14  
**Plan:** `.dev/archive/tts-mic-gate-tail/plan.md` **v1.0** (orchestrator-planning **v0.6**; no §7 amendments)  
**Context map:** pre-plan-exploration **v0.2** @ scout `58f10f132078691a70cc0ae70a5304816fce1f25`  
**Audits:** `.dev/audits/2026-05-21-tts-mic-gate-tail.md` (rev **1** only) → **`pass-with-conditions`** (FIND-01–03 major process; FIND-04 minor doc)  
**Commits (landed):** prep `ac82a086` · T1 `abbaa65f` · T2 `25718245` · T3 `3cfc2052` · closure `e3fd9dc5` (§8 + audit index) · archived `89b7957`  
**One line:** Post-playback acoustic tail on `Speaker.is_playing` (`tts_gate_tail_ms` / `TTS_GATE_TAIL_MS`) — config + `Speaker.speak` sleep + tests + docs — fixing echo transcripts after digital playback ends.

**Artifacts read:** archived `plan.md` (§0–§8), `context-map.md`, packets T1–T3, `.dev/decision-logs/tts-mic-gate-tail-T2.md`, `CHANGELOG.MD` (`tts-mic-gate-tail` section), audit rev 1, `git show` for `ac82a08`, `abbaa65f`, `25718245`, `3cfc2052`, `e3fd9dc`, `89b7957`.

---

## 1. Task identifier

- **Name:** tts-mic-gate-tail  
- **Planning / execution dates:** context map + plan 2026-05-21; T1–T3 same day; audit 2026-05-21; §8 closure `e3fd9dc` 2026-05-21; plan archived 2026-05-23 (`89b7957`)  
- **What it was:** Hold `Speaker.is_playing` through a configurable post-`sd.play` acoustic tail (default 400 ms) before `clear()`, wired via `HecklerConfig.tts_gate_tail_ms` / `TTS_GATE_TAIL_MS`, without changing `AudioCapture`, pacing order, or `tts_latency_ms` semantics.

---

## 2. Plan vs reality

### DAG vs execution

**Matched.** Strict `T1 → T2 → T3`, no parallel groups. Prep commit `ac82a08` landed the plan bundle **before** T1 — execution order still respected config-before-speaker-before-docs.

### Contracts at the implementation surface (§2)

| §2 surface | Enforced in code + test? | Notes |
|------------|--------------------------|-------|
| `tts_gate_tail_ms` / `TTS_GATE_TAIL_MS` | **Yes** | Four config tests (default, override, zero, invalid `ValueError`) |
| Tail after successful `sd.play` | **Yes** | `test_speak_holds_mic_gate_during_post_playback_tail`, `test_speak_zero_tail_skips_post_playback_sleep` |
| Error paths skip tail | **Yes** | Synthesis + play failure tests with sleep recorder |
| `tts_latency_ms` synthesis-only | **Yes** | `test_speak_tts_latency_excludes_post_playback_tail` |
| `AudioCapture` unchanged | **Yes** | No capture diff in T1–T3 commits |
| Error envelope (runtime) | **Yes** | `SpeakerError` on synthesis; play exceptions propagate after `clear` |
| Naming / env literals | **Yes** | README + `.env.example` at T3 |
| Doc↔default sync pytest | **No** | Explicitly deferred in CHANGELOG T3 and plan §8.4 |

**Hollow-contract assessment:** Runtime §2 rows are **not** hollow — each named symbol has a falsifier. The deliberate gap is **markdown hygiene** (no pytest for README/seed prose), waived in writing. No `getattr` defaults or dropped env keys on the typed surface.

### §2 / decision-log narrative survival

- **Context-map flags → plan §0:** All four CONDITIONAL flags resolved before packets — executors did not need mid-flight Flag HALTs. Good.
- **Context map:** Scout inventory describes pre-tail `Speaker.speak` lifecycle (immediate `finally: clear`). Plan §0 and audit **FIND-01** document staleness; roles and coupling surfaces remain valid. **Not repaired** with re-scout (optional per audit).
- **T2 decision log:** Matches landed code at execution time. **Later supersession** (capture-mic-gate-during-play) added a banner that “extend hold in `Speaker` only” was necessary but not sufficient — post-task, not a same-session narrative drift in T2 prose.
- **Plan §8.1 Tree SHA:** Cites **`3cfc2052`** (T3 docs commit) while populated §8 landed in **`e3fd9dc`** — implementation SHA and closure SHA diverge (same family as capture-mic-gate-during-play retro).

### Log tiers

- **T1 `standard`:** Appropriate — single dataclass field + env parse + tests.
- **T2 `architectural`:** Appropriate — gate lifecycle, error-path semantics, decision log, supersession of T8/seed contract.
- **T3 `standard`:** Appropriate for docs; scope also claimed “commit plan bundle” but bundle was already tracked in prep — tier still fits.

Nothing clearly mis-tiered.

### Closure vs committed reality

**Leak (recurring §8-in-HEAD pattern).**

| Checkpoint | What plan / status claimed | What `git show` proved |
|------------|---------------------------|------------------------|
| After **T3** `3cfc2052` | CHANGELOG T3 complete; plan bundle “tracked” | `HEAD:plan.md` §8 still **“Not produced”**; T3 diff is docs only (no plan path) |
| At **audit** (`HEAD` `3cfc2052`) | Working tree: full §8 + *Complete* | `HEAD:plan.md` stub → **FIND-02**, **FIND-03**; §8.1 “clean tree” false while `plan.md` modified |
| After **`e3fd9dc`** | Commit message “done and pass” | `git show e3fd9dc:plan.md` contains §8.1–§8.5 + audit file added — **remediated** |
| **§8.1 Tree SHA** | `3cfc2052` | Correct for **implementation** chain; **incorrect** as first commit containing §8 body (`e3fd9dc`) |
| **Archive `89b7957`** | Plan under `.dev/archive/tts-mic-gate-tail/` | Moves preserve content; audit still references `.dev/plans/...` paths |

Audit ran against **`3cfc2052`** with dirty/uncommitted §8 on disk — correct adversarial discipline (FIND-02/03). **No audit rev 2** after `e3fd9dc` despite closure commit message implying full pass.

**pytest:** **29 passed** @ audit HEAD (`tests/test_config.py`, `tests/test_speaker.py`); plan §8.1 matches.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Zero** in-repo (no HALT transcripts, packet escalations, or decision-log HALT entries). Context-map CONDITIONAL flags were pre-resolved in plan §0; kill criteria functioned as **pre-negotiated** constraints (e.g. no hardcoded ms in `speaker.py`, no tail on error paths).

**False HALT risk:** Low — scope stayed inside `config.py`, `speaker.py`, tests, docs; no `AudioCapture` / `pipeline` / `pacing_gate` creep.

### HALT-shaped silent improvisation

**Yes — closure-shaped, not code-shaped.**

- T3 commit message and CHANGELOG describe a complete doc/plan handoff, but **§8 auditor handoff remained stub in `HEAD`** until **`e3fd9dc`** — same failure mode as transcription-engine v1.0 §8 and capture-mic-gate-during-play (T2 without §8 body).
- Working-tree `plan.md` with *Complete* + §8.1–§8.5 existed **before** `e3fd9dc` while git still said “Not produced” — completion narrative **ahead of** indexed artifacts.
- T3 packet kill criterion (3) (“plan bundle remains untracked”) was **technically satisfied** by prep `ac82a08`, so executor did not re-stage plan paths in T3 — but §8 population was **not** part of T3 commit despite plan status heading toward *Complete*.

### Amendment cycles

**Plan §7:** None declared; none executed.

**Audit-driven remediation:** FIND-02/03 addressed in **`e3fd9dc`** outside §7 — single-purpose closure commit (plan §8 + audit file), **not** a formal amendment subtask. **No re-audit** filed; audit document frozen at rev 1 **`pass-with-conditions`**.

---

## 4. Adversarial pass calibration

### Rejected decompositions (§5.1)

**Held up.**

1. **Hardcoded ms in `speaker.py` only** — Correctly rejected; env-tunable field shipped.
2. **Tail in `AudioCapture`** — Correctly rejected at planning time; later work (`capture-mic-gate-during-play`) showed emit-only skip was insufficient, but that is **complementary** scope, not a bad decomposition of this plan.
3. **Non-blocking play / `sd.wait()` gap** — Correctly rejected; context map and logs validated acoustic bleed, not missing digital wait.

### Load-bearing assumptions (§5.2)

At §8.1 SHA `3cfc2052` (plan §8.4):

- **AudioCapture `is_set()` + Speaker hold** — **closed** in tests at ship time; **later superseded in part** by capture-loop Rule 1 (decision-log banner) — assumption was **necessary but not sufficient** for full echo fix, not a planning error for *this* slice.
- **Pacing `record_output` before `speak`** — **closed** (no pipeline diff).
- **400 ms default** — **treat-as-prediction** (hardware-dependent); env tunable — still correct disposition.
- **T1 before T2 config read** — **closed** (commit order + no hardcoded ms).

### Highest re-plan risk (§5.3)

**T2 — `try`/`finally` + tail-on-success-only:** Did **not** trigger re-plan or amendment. Error-path and tail-hold tests match the packet hint structure. Trouble came from **§8 closure / git index**, not `Speaker.speak` wiring.

### Hidden couplings (§5.4)

| Coupling | Outcome |
|----------|---------|
| `test_speak_clears_event_after_successful_playback` immediate clear | **Closed** — fixture `tts_gate_tail_ms=0` |
| `heckler_seed.md` Coupling Surface 2 | **Closed** at T3 for tail prose; **FIND-04** minor drift on play-error → `SpeakerError` wording in archived seed (~L589) |
| Persona vs transcribe `is_playing` | **Closed** — no controller diff |
| Monkeypatched sleep vs wall clock | **Closed** — `gate_during_tail == [True]` during fake sleep |

---

## 5. Methodology gaps surfaced

### Orchestrator / §8 discipline (recurring)

- **Do not** mark *Complete* or populate §8.1–§8.6 until `git show <cited-sha>:.../plan.md` contains that body — **third** instance in this repo family (transcription-engine, capture-mic-gate-during-play, here).
- **Tree SHA in §8.1** should distinguish **implementation_sha** (`3cfc2052`) from **closure_sha** (`e3fd9dc`) when §8 is appended post-T3.
- T3 scope “commit plan bundle” + prep-already-tracked bundle creates ambiguity: executor satisfied kill (3) via prep but left §8 stub — orchestrator should either require §8 in the **last implementation commit** or declare a **closure subtask** (transcription-engine **T6** pattern).

### Executor

- T3 landed docs but not §8 in the same commit that CHANGELOG calls complete — executor “tracked plan bundle” read as satisfied by prep, not “populate §8 at handoff.”
- **nothing notable** on runtime contract bypass (audit: §2 honored on code surfaces).

### Auditor / amendment pairing

- **`e3fd9dc`** fixes FIND-02/03 but **no audit rev 2** — permanent `pass-with-conditions` understates final git state (same gap noted on capture-mic-gate-during-play retro).
- FIND-04 (seed play-error wording) **recommended**, not blocking — appears **unfixed** in `.dev/archive/heckler_seed.md` at archive time.

### Contracts schema

- **nothing notable** — §2 rows were adequate for this slice.
- Optional: explicit **`closure_sha`** row when §8 is post-dated vs implementation commits.

*(Per skill: do not edit orchestrator/executor/auditor skills from this file.)*

---

## 6. Single sentence verdict

**Partially** — the DAG, §2 runtime contracts, kill-criteria-aligned implementation, and adversarial §5 disposition **held** on code at `3cfc2052`, but **§8 completion leaked** (FIND-02/03) until a **non-§7** closure commit, **without re-audit** and with **implementation_sha vs §8-location mismatch**, so the methodology **did not fully hold** on first closure even though the tail feature is landed and pytest-green.
