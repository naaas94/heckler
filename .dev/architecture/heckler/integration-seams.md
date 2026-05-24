Section:      integration-seams
Version:      1.0.0
Last updated: 2026-05-24

```
Seam:          Local microphone (sounddevice input)
Direction:     inbound
Protocol:      PortAudio via sounddevice; 16 kHz mono float32 stream
Auth:          none (local device)
Data sent:     none
Data received: Raw PCM frames → Silero VAD → AudioChunk segments
Error modes:   Device not found; wrong device index; stream callback exceptions
Retry policy:  none — operator must fix device/config
Owner module:  heckler/audio_capture.py
```

```
Seam:          Local speakers/headphones (sounddevice output)
Direction:     outbound
Protocol:      sounddevice.play blocking @ 24000 Hz (Kokoro output rate)
Auth:          none
Data sent:     Synthesized float audio from Kokoro
Data received: none
Error modes:   Playback failure; device busy
Retry policy:  none — SpeakerError logged; event marked TTS_ERROR
Owner module:  heckler/speaker.py
```

```
Seam:          faster-whisper (local CUDA)
Direction:     inbound (audio) / outbound (text)
Protocol:      Python API WhisperModel.transcribe
Auth:          none — local model weights (~/.cache/huggingface)
Data sent:     AudioChunk.audio numpy array
Data received: Transcript string per segment
Error modes:   CUDA unavailable; model load failure; OOM
Retry policy:  none at seam — startup fails or worker logs exception
Owner module:  heckler/transcriber.py
```

```
Seam:          Silero VAD (torch.hub)
Direction:     inbound
Protocol:      torch.hub.load snakers4/silero-vad
Auth:          none — first run may download from GitHub
Data sent:     512-sample frames @ 16 kHz
Data received: Speech probability per frame
Error modes:   Hub download failure; torch version mismatch
Retry policy:  none
Owner module:  heckler/audio_capture.py
```

```
Seam:          Kokoro TTS (local)
Direction:     outbound
Protocol:      KPipeline(lang_code).__call__(text, voice, speed)
Auth:          none — local pipeline
Data sent:     Comment string
Data received: Audio generator chunks → concatenated ndarray
Error modes:   Synthesis exception → SpeakerError
Retry policy:  none
Owner module:  heckler/speaker.py
```

```
Seam:          LiteLLM → LLM providers (OpenAI default)
Direction:     bidirectional
Protocol:      HTTPS OpenAI-compatible chat completions API
Auth:          API keys via HecklerConfig / env (OPENAI_API_KEY, ANTHROPIC_API_KEY, OLLAMA_API_BASE)
Data sent:     system + user messages (persona system.md, context, utterance)
Data received: Assistant JSON commentary
Error modes:   Network; auth; rate limit; malformed response; refusal
Retry policy:  none in reactor — single attempt; DiscardReason.LLM_ERROR
Owner module:  heckler/reactor.py
```

```
Seam:          SQLite database (local file)
Direction:     bidirectional
Protocol:      stdlib sqlite3; WAL journal
Auth:          filesystem permissions
Data sent:     HeckleEvent rows, transcript chunks, schema version rows
Data received: none (analytics read by external tools)
Error modes:   Disk full; schema version mismatch; locked database
Retry policy:  busy_timeout 30s on connection
Owner module:  heckler/event_store.py, heckler/logger.py, heckler/transcript_store.py
```

```
Seam:          Transcripts markdown export directory
Direction:     outbound
Protocol:      filesystem write under HECKLER_TRANSCRIPTS_DIR (default transcripts/)
Auth:          none
Data sent:     Session markdown on transcribe stop
Data received: none
Error modes:   Permission denied; path missing
Retry policy:  none
Owner module:  heckler/transcript_store.py, heckler/controller.py
```

```
Seam:          Persona prompt bundles (repo filesystem)
Direction:     inbound
Protocol:      Read persona.toml, system.md, examples.json
Auth:          none — trusted local repo content
Data sent:     none
Data received: Persona dataclass fields
Error modes:   PersonaNotFoundError; invalid TOML
Retry policy:  none
Owner module:  heckler/persona.py
```

```
Seam:          Langfuse / LangSmith (optional)
Direction:     outbound
Protocol:      Env-driven LiteLLM tracing callbacks
Auth:          LANGFUSE_* / LANGCHAIN_* / LANGSMITH_* env vars
Data sent:     Completion metadata (when configured)
Data received: none in heckler runtime
Error modes:   Misconfiguration — tracing silently inactive
Retry policy:  none
Owner module:  heckler/reactor.py (_litellm_observability_completion_kwargs)
```

```
Seam:          PyQt6 desktop shell
Direction:     bidirectional (UI ↔ PipelineController)
Protocol:      Qt signals/slots via SignalBridge; in-process callbacks
Auth:          none
Data sent:     User mode/persona/locale choices; start/stop
Data received: Transcripts, reactions, status strings
Error modes:   Thread callback into UI without bridge → crash
Retry policy:  none
Owner module:  heckler/gui/
```
