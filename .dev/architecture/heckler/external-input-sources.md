Section:      external-input-sources
Version:      1.0.0
Last updated: 2026-05-24

```
Source:               Operator microphone (live room audio)
Format:               PCM float32 mono 16 kHz via sounddevice
Parser:               sounddevice InputStream callback + Silero VAD (torch.hub)
Trust level:          untrusted — ambient noise, bleed, other speakers; mitigated by VAD, play-gate, semantic gate
Surfaces extracted:   Speech segments as AudioChunk → transcript text
Surfaces NOT extracted: Audio not passing VAD; segments while is_playing; sub-threshold density utterances (unless LOG_DENSITY_FAILURES)
Volume:               Continuous while pipeline running; bounded queue drops oldest
Sensitivity:          Wrong transcript drives LLM/TTS — user hears incorrect commentary
Owner module:         heckler/audio_capture.py
```

```
Source:               LLM provider response (LiteLLM)
Format:               Chat completion message (string or multipart content)
Parser:               completion_assistant_text + json.loads / regex fallback in reactor
Trust level:          partially trusted — model may deviate from JSON schema; validated before TTS
Surfaces extracted:   comment, score, type → ReactorResult
Surfaces NOT extracted: Raw text on parse failure (logged, LLM_ERROR); sub-threshold scores (SCORE_GATE)
Volume:               One completion per utterance that passes pre-LLM pacing
Sensitivity:          Spoken output to room; persisted in SQLite
Owner module:         heckler/reactor.py
```

```
Source:               Persona bundle files (prompts/<id>/)
Format:               TOML, Markdown, JSON
Parser:               tomllib, plain read_text, json.loads
Trust level:          trusted — repo-controlled; editable by operator
Surfaces extracted:   system_prompt, examples, HecklerConfig overrides, persona metadata
Surfaces NOT extracted: [output].comment_types (informational only per persona.py)
Volume:               Loaded at persona swap / model load
Sensitivity:          Controls voice, gates, and LLM behavior
Owner module:         heckler/persona.py
```

```
Source:               Environment variables and .env file
Format:               KEY=value
Parser:               python-dotenv + os.getenv in load_config
Trust level:          trusted — local operator configuration
Surfaces extracted:   HecklerConfig fields (model, paths, locale, keys, thresholds)
Surfaces NOT extracted: Retired WHISPER_LANGUAGE / raw Kokoro lang env (locale.py is sole speech locale knob)
Volume:               Once per process start; GUI may override locale at reload
Sensitivity:          API keys, database path, model selection
Owner module:         heckler/config.py
```

```
Source:               SQLite database file (optional import / analytics)
Format:               SQLite binary; payload_json + normalized columns
Parser:               External tools / heckle_event_from_json_dict
Trust level:          trusted — local file written by heckler
Surfaces extracted:   Historical HeckleEvent records
Surfaces NOT extracted: audio_chunk (never stored)
Volume:               Append-only per utterance processed
Sensitivity:          Contains transcripts and commentary history
Owner module:         heckler/event_store.py (write); consumers external
```

```
Source:               Transcribe session markdown export
Format:               Markdown file per session
Parser:               Human reader / external tools
Trust level:          trusted — derived from local STT only
Surfaces extracted:   Timestamped chunk text
Surfaces NOT extracted: Audio, LLM output (transcribe mode has no LLM)
Volume:               One file per transcribe session stop
Sensitivity:          Meeting/room speech record
Owner module:         heckler/transcript_store.py
```
