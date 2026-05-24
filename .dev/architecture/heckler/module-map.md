Section:      module-map
Version:      1.0.2
Last updated: 2026-05-24

Granularity: package and module level. Repo scope: `heckler/` package, `prompts/` data bundles, `tests/` (listed for completeness; not product runtime).

| Module path | Role | Key files | Stability |
|-------------|------|-----------|-----------|
| `heckler/` | Package root; version string only | `__init__.py`, `__main__.py` | stable |
| `heckler/pipeline.py` | CLI entry (`main`), threaded workers (transcription / reaction / transcribe), queue topology, gate orchestration | `pipeline.py` | active |
| `heckler/controller.py` | `PipelineController` lifecycle for GUI/CLI: model load, start/stop, mode switch, persona swap, speech-stack reload | `controller.py` | active |
| `heckler/config.py` | `HecklerConfig` dataclass; `load_config()` from `.env`; locale resolution hook | `config.py` | active |
| `heckler/locale.py` | Unified `locale` slug → Whisper language + Kokoro `lang_code` | `locale.py` | active |
| `heckler/models.py` | Pipeline datatypes, enums, `HeckleEvent` JSON helpers | `models.py` | stable |
| `heckler/audio_capture.py` | Mic capture, Silero VAD segmentation, TTS play-gate, bounded `audio_queue` | `audio_capture.py` | active |
| `heckler/transcriber.py` | faster-whisper wrapper (`Transcriber`) | `transcriber.py` | stable |
| `heckler/semantic_gate.py` | Lexical density + min word count pre-LLM filter | `semantic_gate.py` | stable |
| `heckler/context_buffer.py` | Thread-safe rolling transcript context for LLM | `context_buffer.py` | stable |
| `heckler/reactor.py` | LiteLLM completion, JSON parse, score gate, correlation capture | `reactor.py` | active |
| `heckler/pacing_gate.py` | Cooldown between spoken outputs; score override | `pacing_gate.py` | stable |
| `heckler/speaker.py` | Kokoro TTS + sounddevice playback; owns `is_playing` Event | `speaker.py` | active |
| `heckler/persona.py` | Load `prompts/<id>/` bundle; TOML → `HecklerConfig` overrides | `persona.py` | active |
| `heckler/logger.py` | `HecklerLogger` → SQLite `insert_heckle_event_row` | `logger.py` | stable |
| `heckler/event_store.py` | SQLite schema v2, migrations, normalized event columns | `event_store.py` | active |
| `heckler/transcript_store.py` | Transcribe-mode session/chunk tables + markdown export | `transcript_store.py` | stable |
| `heckler/tracing_context.py` | Thread-local correlation dict for LLM traces | `tracing_context.py` | stable |
| `heckler/gui/` | PyQt6 desktop app | `app.py`, `main_window.py` | active |
| `prompts/` | Persona bundles (`persona.toml`, `system.md`, `examples.json`) — not importable package | per-persona dirs | active |
| `tests/` | pytest unit/integration coverage | `test_*.py` | active |

**Notes**

- `pipeline._run_*_worker` functions stay **private-by-convention** (merged review). Sole production consumer is `PipelineController`; tests may import workers directly. If promoted, use a dedicated `heckler/workers.py` with documented contracts — not only removing the underscore. Public seam: `PipelineController` + `ControllerCallbacks`.
- `transcriber.py` exposes `Transcriber.run(in_queue, out_queue)` for tests only; live pipeline calls `transcribe(chunk)` from `_run_transcription_worker`.
- Heavy models (`Transcriber`, `Speaker`) are constructed once per speech-stack signature; hot-swapped `Reactor` via `ReactorHolder` does not reload Whisper/Kokoro unless locale/voice changes.
