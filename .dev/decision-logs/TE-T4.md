# TE-T4 — Pipeline transcribe mode + CLI

**Plan:** transcription-engine v1.0  
**Subtask:** T4 (architectural)

## Chosen approach

- **`main` mode dispatch:** After `load_config()`, `mode = args.mode if args.mode is not None else config.mode`. Branch `mode == "transcribe"` runs capture + Whisper + `transcript_store` only; all persona / reactor / TTS / gates / logger construction stays in the `else` path unchanged.
- **`_run_transcribe_worker`:** Same sentinel pattern as `_run_transcription_worker`; calls `Transcriber.transcribe`, skips empty text, monotonic `sequence_num`, `insert_chunk` under a dedicated `threading.Lock` on the shared SQLite connection.
- **VAD overrides:** `dataclasses.replace(config, max_speech_duration_s=..., silence_duration_ms=..., min_speech_duration_ms=...)` from `transcribe_*` fields; only `AudioCapture` receives `effective_config`; `Transcriber` keeps base `config`.
- **Mic gate:** `threading.Event()` never set → `is_playing.is_set()` is always false in `AudioCapture`’s gate check → mic not suppressed for TTS (there is no TTS in this mode).

## Alternatives rejected

- **Lazy imports for `Reactor` / `Speaker`:** Rejected — modules do not load heavy models at import time (construction only); skipping construction is sufficient and keeps one import surface.
- **Separate entrypoint (e.g. `heckler-transcribe`):** Rejected — breaks the single `python -m heckler` / `main(argv)` contract; `--mode` extends argparse in place.

## Assumptions (load-bearing)

- **`heckler.transcriber` import** does not pull Kokoro or LLM stacks at import time (only `Transcriber.__init__` loads Whisper).
- **`open_store` + `init_transcript_schema`** on the configured DB path is safe alongside any future persona-mode `HecklerLogger` connection (WAL, separate tables).

## Items deferred

- **Markdown export failure semantics:** `export_session_markdown` failures are logged and swallowed in `finally` so shutdown always completes; operators lose export but get a session summary line. Tightening (re-raise, exit code) is a follow-on if product wants hard failure.
- **Adversarial gap:** No automated falsifier for `transcribe_thread.join` timing out while the worker is stuck (same class of gap as persona-mode joins).
