# capture-mic-gate-during-play — T1 — Capture-layer play gate in `_capture_loop`

## Chosen approach

- Module-level `play_gate_frame_tick` + frozen `PlayGateFrameResult` drive per-frame Rule 1: while `is_playing`, discard in-progress `capturing`/`segment`, skip `vad_iter`, and set `was_gated` for the clear edge.
- On the first frame after unmute (`was_gated` and not `is_playing`), preserve capture state, clear `was_gated`, and set `reset_vad` so `_capture_loop` rebuilds `VADIterator` before processing PCM.
- `_emit_audio_segment` early return when `is_playing.is_set()` retained as second defense.
- Max-speech force-flush path discards segment and resets `vad_iter` when `is_playing` is set (defense in depth; normal path `continue`s before VAD while gated).

## Alternatives rejected

- **Emit-only gate (status quo):** rejected — VAD still buffers bleed during play; segments flush after gate clears (validated failure mode in plan context-map).
- **Emit partial user prefix when gate clears mid-segment:** rejected — plan Flag 2 resolution; Rule 1 “if it’s playing, don’t listen” drops the whole overlapping segment.
- **Loop integration test driving `_capture_loop` with Silero hub:** rejected — CI/network/GPU risk; pure helper falsifies state machine (plan Flag 3).

## Assumptions made

- Persona mode continues to pass the same `Speaker.is_playing` `threading.Event` into `AudioCapture` (`controller.py` unchanged).
- Discarding PCM frames while gated (per-frame `continue` before `vad_iter`) prevents post-unmute backlog bleed; deque is drained each iteration but gated frames are not fed to Silero.
- Barge-in during synthesis, playback, or `tts_gate_tail_ms` tail remains blocked by the shared `Event` (tradeoff documented; tail tunable via `TTS_GATE_TAIL_MS`).
- Transcribe mode’s never-set `Event` stays always-open; no refactor of that wiring in T1.

## Items deferred

- **`CHANGELOG.MD` / `heckler_seed.md` prose:** deferred to **T2** per plan DAG (T1 files-to-touch exclude docs).
- **Supersession banner on `tts-mic-gate-tail-T2.md`:** deferred to **T2** (not in T1 files-to-touch).
- **Max-speech flush while `is_playing` without `_capture_loop` mock:** deferred — per-frame `continue` prevents reaching the flush branch while gated; inline discard is defense-in-depth only; no `torch.hub` integration test (kill criterion 3).
