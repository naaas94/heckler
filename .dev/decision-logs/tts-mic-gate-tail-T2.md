# tts-mic-gate-tail — T2 — Speaker post-playback mic-gate tail

## Chosen approach

- After successful `sd.play(..., blocking=True)`, if `self._config.tts_gate_tail_ms > 0`, call `time.sleep(tail_ms / 1000.0)` inside the playback `try` before `finally` clears `is_playing`.
- Synthesis failures clear in the synthesis `except` (unchanged); `sd.play` exceptions skip the sleep body but still hit `finally` → immediate clear without tail.
- `speak()` return value remains synthesis wall time only (`perf_counter` bracket ends before playback/tail).
- Unit tests monkeypatch `speaker_mod.time.sleep` and use `tts_gate_tail_ms=0` on the default fixture so legacy “immediate clear” paths stay fast and deterministic.

## Alternatives rejected

- **Tail sleep in `finally` after `clear()`:** rejected — would ungate the mic before the acoustic buffer elapses, defeating the echo fix.
- **Moving tail into `AudioCapture` or reactor dedup:** rejected — plan non-goals; gate extension in `Speaker.speak` is the single choke point shared with persona mode.
- **Including tail in `tts_latency_ms`:** rejected — contract and metrics would conflate synthesis latency with intentional hold time.

## Superseded assumption

- **Prior assumption:** “`AudioCapture` continues to suppress segments while `is_playing.is_set()`; extending hold in `Speaker` is sufficient without capture changes.”
- **Superseded by:** `capture-mic-gate-during-play` — emit-only enqueue skip left Silero VAD buffering bleed during play; capture-loop **Rule 1** (`play_gate_frame_tick` in `_capture_loop`) is required. **Post-playback tail in `Speaker.speak` remains valid** and complementary (decision log: `.dev/decision-logs/capture-mic-gate-during-play-T1.md`).

## Assumptions made

- ~~`AudioCapture` continues to suppress segments while `is_playing.is_set()`; extending hold in `Speaker` is sufficient without capture changes~~ — **superseded** (see banner above); tail-only hold was necessary but not sufficient.
- Default **400 ms** is adequate for typical speaker bleed; reverberant setups may need `TTS_GATE_TAIL_MS` tuning (T3 docs).
- `PacingGate.record_output()` timing stays at speak intent, not playback end — tail does not move that call (frozen in `_execute_spoken_reply`).

## Items deferred

- **Negative or absurdly large `TTS_GATE_TAIL_MS` values:** deferred — T1 uses bare `int(os.getenv(...))`; `tail_ms > 0` guard only skips zero, not validation of upper bounds (operator/env responsibility).
- **Adversarial falsifier for wrong tail unit (e.g. sleep ms instead of seconds):** covered by `test_speak_holds_mic_gate_during_post_playback_tail` asserting `sleep(0.4)` for `400` config; no separate test for mis-typed divisor.

## Supersedes

- Prior behavior: `is_playing` cleared immediately when digital playback ended.
- New behavior: cleared after playback **and** configurable post-playback acoustic tail (`tts_gate_tail_ms`).
