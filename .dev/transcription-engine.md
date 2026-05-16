# Direction 2: Transcription Engine (Transcribe-Only Mode)

## Status: Design — not yet implemented

## Summary

A standalone mode that uses heckler's audio capture + Whisper pipeline purely as a transcription engine. No LLM, no TTS, no gates. Audio input is continuously transcribed in chunks, correlated to a session/thread ID, and streamed or persisted to disk. Use case: recording interviews, lectures, meetings, personal logs — anything where you want a text archive of what was said without holding it all in memory.

## Current Architecture (what we're branching from)

The existing pipeline is tightly coupled to the full heckler loop:

```
Mic → VAD → Whisper → DensityGate → Reactor(LLM) → ScoreGate → PacingGate → Kokoro TTS
```

- **AudioCapture**: `sounddevice.InputStream` → Silero VAD → `AudioChunk` → `audio_queue`. Already self-contained.
- **Transcriber**: `faster_whisper.WhisperModel` on CUDA. `transcribe(chunk)` returns text. Also self-contained.
- **DensityGate** (`semantic_gate.passes_gate`): filters low-content utterances. Useful for heckler (skip mumbling), counterproductive for transcription (you want everything).
- **Reactor / Speaker / PacingGate**: the entire back half — not needed, and loading these models wastes VRAM and startup time.
- **HeckleEvent / event_store**: schema is reactor-centric (score gates, comment types, TTS latency). Doesn't fit transcription chunks.

## Design Decisions

### Pipeline mode split

The pipeline gets a mode concept. CLI: `--mode persona` (default, current behavior) vs `--mode transcribe`. In transcribe mode:
- **Load**: AudioCapture + Transcriber only. No Reactor, no Speaker, no Kokoro model load.
- **Skip**: density gate, score gate, pacing gate — all bypassed.
- **Output**: transcribed text → persistence layer (disk), not reaction queue.

This means faster startup (no TTS/LLM model loading) and lower VRAM usage.

### Session / thread ID concept

Each transcription run is a **session**: a UUID (or user-provided name) that groups all chunks from one recording. This solves the "long utterance" problem — chunks are persisted individually as they arrive, correlated by session ID. Nothing accumulates in memory.

```
Session: "interview-2026-05-16"
  ├── chunk 1: "So tell me about your experience with..." (00:00:12)
  ├── chunk 2: "I've been working in distributed systems..." (00:00:28)
  ├── chunk 3: "The main challenge was..." (00:01:04)
  └── ...
```

### Persistence

Two complementary outputs (not mutually exclusive):

**SQLite** (structured, queryable — alongside or separate from existing heckler.db):

```sql
CREATE TABLE transcript_sessions (
    id TEXT PRIMARY KEY,          -- uuid or user-provided slug
    name TEXT,                    -- human-readable label
    started_at TEXT NOT NULL,     -- ISO 8601
    ended_at TEXT                 -- set on session close
);

CREATE TABLE transcript_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES transcript_sessions(id),
    chunk_text TEXT NOT NULL,
    timestamp_iso TEXT NOT NULL,  -- when this chunk was captured
    duration_s REAL,              -- audio duration of source chunk
    sequence_num INTEGER          -- ordering within session
);
```

**Flat file export** (human-readable archive):

```
transcripts/
  2026-05-16_interview-name.md
```

Format: timestamped paragraphs, one per chunk. Written incrementally (append mode) so partial sessions survive crashes:

```markdown
# interview-name — 2026-05-16

[00:00:12] So tell me about your experience with...

[00:01:04] I've been working in distributed systems for about five years now...

[00:02:30] The main challenge was keeping consistency across regions without...
```

### VAD tuning for transcription

Heckler's VAD is tuned for short reactive utterances:
- `max_speech_duration_s = 15.0` — forces flush at 15s.
- `silence_duration_ms = 800` — short silence = end of utterance.
- `min_speech_duration_ms = 500` — ignores very short sounds.

For transcription (interviews, lectures), these need to be different:
- **Longer max duration**: 30–60s chunks, or even unbounded with periodic flush.
- **Longer silence threshold**: 1500–2000ms — don't split mid-thought on a brief pause.
- **Lower min speech duration**: capture even short responses ("yes", "no").

These overrides could live in the persona/mode config. In transcribe mode, a different set of defaults applies automatically. User can still override via env or GUI.

### Mic gate behavior

In persona mode, `AudioCapture` skips enqueue while TTS is playing (`speaker.is_playing` event). In transcribe mode, there's no speaker — the mic gate is always open. The `is_playing` event simply stays unset (never blocks).

## GUI Surface — PyQt6

Transcription mode in the same PyQt6 launcher:
- **Mode toggle**: switch between Persona and Transcribe modes.
- **Session controls**: start/stop recording, name the session, see elapsed time.
- **Live transcript feed**: rolling text area showing chunks as they arrive. Each chunk timestamped.
- **Export**: save session as markdown file or copy to clipboard.
- **Session history**: list past sessions, reopen/view them.

## Relationship to Persona System

These two directions are **orthogonal but share infrastructure**:
- Same `AudioCapture` and `Transcriber` modules.
- Same PyQt6 shell (mode toggle switches the active pipeline variant).
- Transcribe mode doesn't use `Persona` at all — no LLM, no prompts.
- But a hypothetical "transcribe + summarize" mode could combine both: transcribe first, then run the transcript through an LLM persona for notes/summaries. That's a future extension, not in scope now.

## Implementation Plan

1. **Transcript persistence**: new `heckler/transcript_store.py` — SQLite schema for sessions + chunks, flat-file writer.
2. **Transcription-only pipeline path**: new worker function (or mode branch in `pipeline.py`) that skips Reactor/Speaker/gates.
3. **CLI mode flag**: `--mode transcribe` (or `--transcribe-only`) on `argparse`.
4. **VAD config overrides**: transcribe-mode defaults for longer chunks, longer silence, etc.
5. **Session management**: start/stop/name sessions, generate session IDs.
6. **PyQt6 integration**: transcribe tab in the launcher with live feed + session controls.

## Open Questions

- **Speaker diarization**: should the transcription engine try to distinguish speakers? Whisper doesn't natively do this, but post-processing with `pyannote.audio` or similar is possible. Deferred — adds significant complexity and a heavy model dependency.
- **Chunk overlap**: should consecutive chunks overlap slightly to avoid word-boundary splits? Whisper's VAD filter handles this somewhat, but edge cases exist. Monitor in practice.
- **Audio archival**: should raw audio chunks be saved alongside text? Useful for re-transcription with better models later. Storage cost is high. Optional flag, off by default.
- **Real-time streaming vs batch**: current architecture is chunk-based (VAD detects speech end → transcribe). True streaming (partial results as speech happens) would need a different Whisper integration (e.g. `whisper_streaming`). Chunk-based is fine for archival; streaming is better for live display. Decide based on latency requirements.
