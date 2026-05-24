# Heckler — next steps

Tracked backlog from notes (`thoughts_so_far.md`, `gui_thougths.md`), eval docs, and commit/changelog audit (last ~86 commits). Check off as you land work.

**Related specs:** [`.dev/persona-capture-vad.md`](.dev/persona-capture-vad.md) · [`.dev/eval-strategy.md`](.dev/eval-strategy.md) · [`GUI_DARK_THEME.md`](GUI_DARK_THEME.md)

---

## P1 — Capture & echo

Mic gates during play + post-playback tail are **landed**; technician monologues and echo LLM waste are still open.

- [ ] **Persona `[capture]` in TOML** — map `max_speech_duration_s`, `silence_duration_ms`, `min_speech_duration_ms` in `heckler/persona.py`; tests; add block to `prompts/technician/persona.toml` (45 s / 2000 ms per spec)
- [ ] **Hot-swap / running capture** — document or implement whether `swap_persona` applies new VAD without restart (see persona-capture-vad § Hot-swap)
- [ ] **Echo re-validation** — session pass after capture gate + tail + pre-LLM pacing; confirm bleed rate in SQLite/logs
- [ ] **Echo skip before reactor** — skip `react()` when transcript ≈ last spoken comment (needs `last_spoken` or similar state on pipeline/speaker)
- [ ] **Operator echo hygiene** — headphones / routing / gain guidance in README or runbook (optional AEC if speakers + mic)

---

## P2 — Eval & analytics

SQLite v2 + `.dev/eval-strategy.md` are **landed**; human-in-the-loop workflow is not.

- [ ] **`heckler_eval_labels` writer** — CLI or script: `event_id`, `human_quality` ∈ positive | negative | skip, optional `extra_json` / rater
- [ ] **Stratified export** — SQL view or script joining `events` ⋈ `event_reactor_results` ⋈ labels; cohorts per eval-strategy §4 (spoken, pre/post-LLM pacing, score bands)
- [ ] **Score-gate near-miss persistence** (optional) — config flag: keep sub-threshold `ReactorResult` with `passed_score_gate = 0`, `discard_reason = score_gate`
- [ ] **Context on events** (optional) — fingerprint or last-*k* context snippet for callback labeling
- [ ] **Version stamp on events** (optional) — model id, `SCORE_THRESHOLD`, prompt asset hash in `correlation_json` or dedicated columns
- [ ] **Insert-failure guardrails** — metric or log when SQLite insert fails; sanity check row count vs session length
- [ ] **Semantic surface analysis** — exploratory pass on density/score/comment_type distributions (no tooling in repo yet)
- [ ] **Calibration slice** — re-label fixed small set after major prompt changes

---

## P3 — GUI & operator UX

`heckler-gui` is **landed**; theme and log UX are not.

- [ ] **Dark theme** — implement per [`GUI_DARK_THEME.md`](GUI_DARK_THEME.md) (Fusion palette, QSS, Windows title bar; one PR)
- [ ] **Backend / full log tab** — timestamps, gate flags, latencies, discard reasons (main events vs full trace — pick one)
- [ ] **Richer operator logs** — readable export or in-app view beyond live transcript/reaction feed
- [ ] **Larger status message** — lower-left status bar prominence (`gui_thougths.md`)
- [ ] **Transparency / acrylic** — deferred; out of scope for dark-theme spec unless explicitly revived

---

## P4 — Memory & context product

`ContextBuffer` (rolling window) is **landed**; durable memory is not.

- [ ] **Memory model definition** — what persists across sessions vs per-utterance context
- [ ] **Certified classics** (optional) — curated examples replacing or augmenting per-persona few-shots
- [ ] **Operational memory workflow** — how operators add, prune, and trust memory day to day

---

## P5 — CI & platform

- [ ] **CI surface** — GitHub Actions (or equivalent): `pytest` on PR, optional headless GUI smoke with `QT_QPA_PLATFORM=offscreen`

---

## Done — no action unless regressing

Use this section only to avoid re-planning shipped work.

- [x] Core persona pipeline (capture → Whisper → semantic gate → reactor → pacing → TTS → SQLite)
- [x] LiteLLM multi-provider; Langfuse/LangSmith metadata on live rows
- [x] SQLite event decomposition (`events`, `event_reactor_results`, `heckler_eval_labels` DDL)
- [x] Legacy JSONL import; persona system; transcribe mode + markdown export
- [x] PyQt6 GUI launcher (`heckler-gui`); locale propagation; persona speech-stack reload
- [x] TTS mic-gate tail; capture play-gate during playback; pre-LLM pacing skip
- [x] Per-persona `pacing_interval` in TOML (e.g. technician @ 6 s; heckler @ 12 s)
- [x] System prompt / few-shot refresh (early examples pass)
- [x] Technician persona bundle (prompts/gates/voice) — **without** `[capture]` overrides yet

---

## Notes

- **`thoughts_so_far.md`** — raw observations (echo symptoms, score bands); keep for debugging, not as the task list.
- **`gui_thougths.md`** — GUI wish list; items above subsume it except typo in filename.
- Revisit priorities after P1 capture + echo skip — they unblock technician UX and cheaper sessions.
