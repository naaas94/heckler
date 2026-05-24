Section:      public-interface-inventory
Version:      1.0.1
Last updated: 2026-05-24

Symbols that cross module boundaries or are entry points for external callers (CLI, GUI, tests).

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `main` | `heckler/pipeline.py` | function | CLI argparse; starts persona or transcribe pipeline | `pyproject` script `heckler`, `__main__` | stable |
| `PipelineController` | `heckler/controller.py` | class | Lifecycle: `load_models`, `start`, `stop`, `switch_mode`, `swap_persona`, speech reload | `heckler/gui/main_window.py`, tests | active |
| `ReactorHolder` | `heckler/controller.py` | class | Thread-safe `Reactor` swap between utterances | `pipeline`, `controller` | active |
| `ControllerCallbacks` | `heckler/controller.py` | dataclass | `on_transcript`, `on_reaction`, `on_status`, `on_error` | GUI | active |
| `SpeechReloadPolicy` | `heckler/controller.py` | enum | `auto` / `ask` / `never` for locale/persona reload UX | GUI | active |
| `HecklerConfig` | `heckler/config.py` | dataclass | Frozen runtime configuration snapshot | most modules | active |
| `load_config` | `heckler/config.py` | function | Load `.env` → `HecklerConfig` with locale resolution | CLI, GUI, tests | stable |
| `apply_resolved_locale` | `heckler/config.py` | function | Map `locale` → `whisper_language`, `kokoro_lang_code` | config, persona, controller | stable |
| `resolve_locale` | `heckler/locale.py` | function | Slug → `LocaleProfile`; raises `UnsupportedLocaleError` | config | stable |
| `speech_stack_signature` | `heckler/locale.py` | function | `(whisper_language, kokoro_lang_code)` tuple for reload compare | controller, GUI | stable |
| `SUPPORTED_LOCALES` | `heckler/locale.py` | constant | Dict of locale slugs | locale, GUI | active |
| `AudioChunk` | `heckler/models.py` | dataclass | float32 16 kHz audio + `captured_at` | capture → transcriber | stable |
| `Utterance` | `heckler/models.py` | dataclass | Transcript + density + id; carries `AudioChunk` | pipeline workers | stable |
| `ReactorResult` | `heckler/models.py` | dataclass | LLM comment, score, type, raw response | reactor, pipeline, GUI | stable |
| `HeckleEvent` | `heckler/models.py` | dataclass | Full pipeline outcome record for persistence | logger, event_store | stable |
| `serialize_heckle_event` | `heckler/models.py` | function | JSON-safe dict; strips `audio_chunk` | logger | stable |
| `CommentType` | `heckler/models.py` | enum | Commentary style labels | reactor, models | stable |
| `DiscardReason` | `heckler/models.py` | enum | Gate/error discard causes | pipeline, models | stable |
| `AudioCapture` | `heckler/audio_capture.py` | class | Threaded mic + VAD → `audio_queue` | pipeline, controller | active |
| `play_gate_frame_tick` | `heckler/audio_capture.py` | function | Pure play-gate state machine per VAD frame | audio_capture (internal), tests | stable |
| `_put_drop_oldest` | `heckler/audio_capture.py` | function | Bounded queue policy (drop oldest on full) | pipeline, audio_capture | stable |
| `Transcriber` | `heckler/transcriber.py` | class | `transcribe(AudioChunk) -> str` (production); `run(in_queue, out_queue)` test-only orphan | pipeline, controller, tests | stable |
| `passes_gate` | `heckler/semantic_gate.py` | function | `(passes, density)` from text + config | pipeline | stable |
| `compute_density` | `heckler/semantic_gate.py` | function | Lexical density ratio | tests, semantic_gate | stable |
| `ContextBuffer` | `heckler/context_buffer.py` | class | `push`, `get_context_block` | pipeline, controller | stable |
| `Reactor` | `heckler/reactor.py` | class | `react(utterance, context_block) -> (result, ms, discard)` | pipeline via holder | active |
| `completion_assistant_text` | `heckler/reactor.py` | function | Extract text from LiteLLM response shape | reactor, tests | stable |
| `PacingGate` | `heckler/pacing_gate.py` | class | `cooldown_status`, `evaluate`, `record_output` | pipeline | stable |
| `Speaker` | `heckler/speaker.py` | class | `speak(comment) -> tts_latency_ms`; exposes `is_playing` | pipeline, controller | active |
| `SpeakerError` | `heckler/speaker.py` | exception | TTS synthesis failure | pipeline | stable |
| `Persona` | `heckler/persona.py` | dataclass | Loaded bundle: prompts + overrides | controller, pipeline | active |
| `load_persona` | `heckler/persona.py` | function | `Path` → `Persona` | controller, pipeline | stable |
| `list_personas` | `heckler/persona.py` | function | Enumerate ids under `prompts/` | GUI | stable |
| `apply_persona_overrides` | `heckler/persona.py` | function | Merge persona TOML into `HecklerConfig` | controller | stable |
| `HecklerLogger` | `heckler/logger.py` | class | `log_event(HeckleEvent)` → SQLite | pipeline | stable |
| `open_store` | `heckler/event_store.py` | function | Open SQLite with WAL pragmas | logger, controller, tests | stable |
| `init_schema` | `heckler/event_store.py` | function | Heckler events schema v2 + migration | logger | active |
| `insert_heckle_event_row` | `heckler/event_store.py` | function | Normalized + JSON payload insert | logger | active |
| `insert_event_row` | `heckler/event_store.py` | function | Legacy JSON-only row insert | tests, tooling | stable |
| `SCHEMA_VERSION` | `heckler/event_store.py` | constant | Current heckler DB schema int (2) | migrations | active |
| `init_transcript_schema` | `heckler/transcript_store.py` | function | Transcribe tables | controller, pipeline | stable |
| `create_session` / `close_session` | `heckler/transcript_store.py` | function | Transcribe session lifecycle | controller | stable |
| `insert_chunk` | `heckler/transcript_store.py` | function | Persist transcribe utterance | pipeline transcribe worker | stable |
| `export_session_markdown` | `heckler/transcript_store.py` | function | Write `transcripts/*.md` | controller on stop | stable |
| `set_correlation` / `get_correlation` / `clear_correlation` | `heckler/tracing_context.py` | function | Thread-local trace metadata | reactor, logger | stable |
| `main` | `heckler/gui/app.py` | function | Qt app entry | `heckler-gui` script | active |
| `HecklerMainWindow` | `heckler/gui/main_window.py` | class | Main window + `SignalBridge` | GUI app | active |
| `ModelLoadThread` | `heckler/gui/app.py` | class | Background model load | GUI | active |

**Private-by-convention (not public API — Phase 8)**

| Symbol | Module | Consumed by | Note |
|--------|--------|-------------|------|
| `_run_transcription_worker` | `pipeline.py` | `controller.py`, tests | Thread target; do not export without controller contract |
| `_run_reaction_worker` | `pipeline.py` | `controller.py`, tests | Same |
| `_run_transcribe_worker` | `pipeline.py` | `controller.py`, tests | Same |
| `_execute_spoken_reply` | `pipeline.py` | `pipeline.py` | Coupling surface 6 enforcement |

**Recommended public seam for new integrators:** `PipelineController` + `ControllerCallbacks`, not `_run_*_worker`.
