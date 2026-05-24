Section:      data-contract-registry
Version:      1.0.0
Last updated: 2026-05-24

```
Contract:       AudioChunk
Module:         heckler/models.py
Serialization:  dataclass (in-memory); numpy array not JSON-serialized
Version:        unversioned — tracked by git blame
Purpose:        Single VAD segment passed from capture to Whisper
Fields:
  - audio: float32 ndarray shape (N,) — 16 kHz mono PCM
  - captured_at: float — time.time() at segment boundary
Validators:     Producer must use 16 kHz; consumer assumes float32 1D (coupling surface 1)
Consumers:      heckler/audio_capture.py, heckler/transcriber.py, heckler/pipeline.py
Last changed:   2026-05-24
```

```
Contract:       Utterance
Module:         heckler/models.py
Serialization:  dataclass (in-memory only on reaction_queue)
Version:        unversioned — tracked by git blame
Purpose:        Post-gate unit of work for LLM reaction worker
Fields:
  - utterance_id: str (uuid4)
  - transcript: str
  - semantic_density: float
  - transcribed_at: float
  - audio_chunk: AudioChunk — retained for debug/future use; not persisted on HeckleEvent
Validators:     Created only after semantic gate passes
Consumers:      heckler/pipeline.py, heckler/reactor.py
Last changed:   2026-05-24
```

```
Contract:       ReactorResult
Module:         heckler/models.py
Serialization:  dataclass; nested in HeckleEvent JSON as plain dict
Version:        unversioned — tracked by git blame
Purpose:        Parsed LLM commentary when score gate passes
Fields:
  - comment: str — text sent to TTS
  - score: float — 0.0–1.0 self-assessed
  - comment_type: CommentType enum
  - raw_response: str — verbatim model output for logging
Validators:     reactor._parse_response: comment str, score in [0,1], valid CommentType
Consumers:      heckler/reactor.py, heckler/pipeline.py, heckler/gui, heckler/event_store (child row)
Last changed:   2026-05-24
```

```
Contract:       HeckleEvent
Module:         heckler/models.py
Serialization:  dataclass → serialize_heckle_event() → JSON text in SQLite payload_json + normalized columns
Version:        unversioned — tracked by git blame; SQLite heckler_schema_version=2 for storage shape
Purpose:        Auditable record of each processed utterance (pass/fail at each gate)
Fields:
  - utterance_id, timestamp_iso, transcript, semantic_density: identity and input
  - passed_density_gate: bool
  - reactor_result: Optional[ReactorResult]
  - passed_score_gate, passed_pacing_gate: Optional[bool] — None when not evaluated
  - spoken: bool
  - discard_reason: Optional[DiscardReason]
  - cooldown_remaining_at_eval, llm_latency_ms, tts_latency_ms: Optional metrics
Validators:     heckle_event_json_round_trip in tests; audio_chunk stripped on serialize
Consumers:      heckler/logger.py, heckler/event_store.py, analytics/export tooling
Last changed:   2026-05-24
```

```
Contract:       LLM response JSON (reactor parse target)
Module:         heckler/reactor.py (parser); declared in prompts/*/system.md
Serialization:  JSON object in assistant message text
Version:        unversioned — tracked by git blame + prompt bundle
Purpose:        Structured commentary from LiteLLM completion
Fields:
  - comment: str
  - score: float [0, 1]
  - type: str — must match CommentType.value
Validators:     json.loads + regex fallback; score gate in Reactor.react
Consumers:      heckler/reactor.py
Last changed:   2026-05-24
```

```
Contract:       Persona bundle (filesystem)
Module:         prompts/<persona_id>/
Serialization:  TOML + Markdown + JSON files
Version:        unversioned — per-persona git blame
Purpose:        Voice/LLM/gate overrides and prompt content for Reactor
Fields:
  - persona.toml: [persona], [voice], [llm], [gates], [output] tables
  - system.md: system prompt text
  - examples.json: list of example dicts for few-shot block
Validators:     load_persona: required [persona].name; TOML keys mapped via _TOML_TO_CONFIG
Consumers:      heckler/persona.py, heckler/controller.py, heckler/pipeline.py
Last changed:   2026-05-24
```

```
Contract:       HecklerConfig
Module:         heckler/config.py
Serialization:  frozen dataclass; env vars via load_config()
Version:        unversioned — tracked by git blame
Purpose:        Single runtime configuration object threaded through pipeline
Fields:
  - Audio/VAD: sample_rate, vad_threshold, min/max speech, silence ms
  - Speech stack: locale, whisper_*, kokoro_*
  - Gates: density_threshold, min_word_count, score_*, min_output_interval_s
  - LLM: llm_model, tokens, temperature, API key fields
  - Storage: sqlite_database_path, transcripts_dir, mode, persona_name
Validators:     apply_resolved_locale on locale; persona apply_persona_overrides subset
Consumers:      all heckler modules
Last changed:   2026-05-24
```

```
Contract:       TranscriptSession / TranscriptChunk
Module:         heckler/transcript_store.py
Serialization:  dataclass + SQLite tables (transcript_schema_version=1)
Version:        unversioned — tracked by git blame
Purpose:        Transcribe-mode session persistence and markdown export
Fields:
  - session: id, name, started_at, ended_at
  - chunk: session_id, chunk_text, timestamp_iso, duration_s, sequence_num
Validators:     init_transcript_schema version check
Consumers:      heckler/pipeline.py (_run_transcribe_worker), heckler/controller.py
Last changed:   2026-05-24
```

```
Contract:       Correlation metadata
Module:         heckler/tracing_context.py
Serialization:  dict[str, str] → JSON correlation_json column
Version:        unversioned — tracked by git blame
Purpose:        Link SQLite events to LiteLLM/hosted trace ids when available
Fields:         completion_id, model, system_fingerprint, etc. (optional strings)
Validators:     Scalar strings only from completion response
Consumers:      heckler/reactor.py, heckler/logger.py
Last changed:   2026-05-24
```

```
Contract:       Context block (ephemeral string)
Module:         heckler/context_buffer.py
Serialization:  plain text, numbered lines [1]..[N]
Version:        unversioned — tracked by git blame
Purpose:        Recent utterances embedded in LLM user message
Fields:         N = config.context_window_size transcripts
Validators:     none
Consumers:      heckler/reactor.py
Last changed:   2026-05-24
```
