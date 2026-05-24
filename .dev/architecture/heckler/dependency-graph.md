Section:      dependency-graph
Version:      1.2.0
Last updated: 2026-05-24

## Internal dependencies

Non-obvious structural coupling beyond single-direction imports.

| Dependent | Depends on | Nature of coupling | Risk if changed independently |
|-----------|-----------|--------------------|------------------------------|
| `pipeline.py` | `controller.py` types | `ReactorHolder` TYPE_CHECKING only; `main()` lazy-imports `PipelineController` | Eager mutual import at module level breaks startup |
| `controller.py` | `pipeline.py` workers | Imports `_run_*` at import time — sole production consumer | Renaming workers breaks GUI/CLI |
| `audio_capture.py` | `speaker.py` (runtime) | Shared `is_playing` Event at construction | Wrong Event → TTS bleed |
| `pipeline.py` | `pacing_gate` + `speaker` | `record_output()` before `speak()` via `_execute_spoken_reply` | Cooldown drift |
| `reactor.py` | `prompts/*` | JSON schema + examples.json shape (not import) | LLM_ERROR / bad few-shots |
| `persona.py` | `config.py` | `_TOML_TO_CONFIG` | Silent ignore of overrides |
| `logger.py` | `tracing_context` | Correlation on reaction thread at log time | Stale correlation if thread moves |
| `event_store` | `models` | `_EVENT_ANALYTICS_COLUMNS` mirrors `HeckleEvent` | Migration on field change |
| `scripts/import_legacy_jsonl.py` | `event_store` privates | Imports `_EVENT_ANALYTICS_COLUMNS`, `_heckle_event_analytics_params` | Import script breaks on refactor |
| `gui/main_window` | `controller` | `SignalBridge` + `PipelineController` | Direct widget mutation from workers breaks Qt |
| `locale` | `config` | resolve at load; GUI `_LOCALE_DISPLAY` parallel table | Locale drift GUI vs locale.py |

**Import graph (runtime):** Not bidirectional at import time, but **architecturally mutual**: `controller` → `pipeline` at load; `pipeline` → `controller` only inside `main()`. CLI/GUI should not treat `pipeline` as independent of controller lifecycle.

**Logical bidirectionality:** `speaker` ↔ `audio_capture` via Event; `reactor` ↔ `prompts` via schema string contract.

**Dual config snapshot:** `load_models(target_speech_config)` builds Transcriber/Speaker; `start()` applies `apply_persona_overrides` for session workers/Reactor/logger config. Voice-only persona change may not require reload (voice ∉ `speech_stack_signature`).

**Dead API:** `Transcriber.run` — tests only; production uses `transcribe(chunk)`.

**Play vs synthesis errors:** `SpeakerError` / `TTS_ERROR` on synthesis only; `sd.play` failures clear gate but propagate (see failure-taxonomy `L5.tts_playback_failure`).

## Shared runtime state (not in import graph)

| State | Threads / owners | Risk |
|-------|------------------|------|
| `audio_queue` / `reaction_queue` | capture → transcription → reaction | Stop: join transcription before reaction sentinel |
| `ReactorHolder._reactor` + lock | GUI swap vs reaction `get()` | Swap mid-utterance serialized per item |
| `PacingGate._last_output_time` | reaction worker only | Lock-protected |
| `ContextBuffer` | reaction worker `push` after each utterance | Missing push on new continue branches |
| `Speaker.is_playing` | speaker vs capture | Wrong Event instance |
| `HecklerLogger._conn` + `_lock` | reaction worker inserts | Re-raise on insert failure |
| `tracing_context` | reaction worker thread-local | Must not log events from other threads without set |
| `transcript_conn` + `transcript_lock` | transcribe worker | Same DB file as heckle events |
| **Two schema version tables** | `heckler_schema_version` vs `transcript_schema_version` | One file, separate migration policies |
| GUI `SignalBridge` | Qt main ↔ workers | Thread boundary |

**Stop ordering (persona):** `controller.stop()` joins `heckler-transcription` before enqueueing reaction `None` sentinel, then joins `heckler-reaction` — implicit coupling to thread list order.

## External dependencies

From `pyproject.toml` (runtime). CUDA torch installed separately per README.

| Dependency | Version pinned | Role in project | Sensitivity |
|------------|---------------|-----------------|-------------|
| `sounddevice` | >=0.4.6 | Mic input and speaker output | medium — device index instability on Windows |
| `numpy` | >=1.26,<2 | Audio buffers | high — ABI breaks with torch stack if bumped to 2.x |
| `faster-whisper` | >=1.0.3 | STT (CUDA in transcriber.py) | medium — device hardcoded cuda today |
| `litellm` | >=1.40.0 | LLM routing | medium — response shape drift |
| `kokoro` | >=0.9.2 | TTS KPipeline | high |
| `torch` / `torchaudio` | >=2.5.0 | Silero hub + Kokoro | high |
| `python-dotenv` | >=1.0.0 | `.env` loading | low |
| `PyQt6` | >=6.5 | GUI | medium |
| Silero VAD (hub) | not in pyproject | `torch.hub.load` | medium |

**External services (runtime)**

| Service | Role | Sensitivity |
|---------|------|-------------|
| OpenAI / Anthropic / Ollama (LiteLLM) | Persona commentary | high — no retry at seam |
| Hugging Face cache | Whisper weights | low after first fetch |
| Langfuse / LangSmith (optional) | Traces | low — misconfig silent no-op |
