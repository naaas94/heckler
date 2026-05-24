Section:      known-coupling-surfaces
Version:      1.2.0
Last updated: 2026-05-24

Binding points invisible from import graph alone. Count is editorial; substance overlaps across construction passes.

```
Surface:      _put_drop_oldest queue overflow policy
Shared by:    heckler/audio_capture.py ↔ heckler/pipeline.py (workers + shutdown sentinel)
Failure mode: Different overflow behavior between capture emit and worker enqueue
Confirmed:    yes
```

```
Surface:      AudioChunk.audio dtype and shape
Shared by:    heckler/audio_capture.py (producer) ↔ heckler/transcriber.py (consumer)
Failure mode: Wrong dtype/shape → garbage or failed Whisper transcripts
Confirmed:    yes — models.py + audio_capture._emit_audio_segment
```

```
Surface:      speaker.is_playing threading.Event
Shared by:    heckler/speaker.py ↔ heckler/audio_capture.py (wired in controller._start_persona_mode)
Failure mode: TTS bleed / echo transcribed → recursive heckle
Confirmed:    yes — transcribe mode uses unset Event (no Speaker)
```

```
Surface:      pacing_gate.record_output() before speaker.speak()
Shared by:    heckler/pipeline._execute_spoken_reply ↔ heckler/pacing_gate ↔ heckler/speaker
Failure mode: Cooldown skew vs audio duration
Confirmed:    yes — coupling surface 6
```

```
Surface:      capture 16000 Hz + VAD_FRAME_SAMPLES=512
Shared by:    HecklerConfig.sample_rate, Silero hub, Whisper
Failure mode: VAD/Whisper mis-segmentation; ValueError if sample_rate != 16000 at capture start
Confirmed:    yes
```

```
Surface:      Kokoro output 24000 Hz playback
Shared by:    heckler/speaker.speak ↔ sounddevice.play(samplerate=24000)
Failure mode: Pitch/speed wrong if Kokoro API or playback rate changes
Confirmed:    yes
```

```
Surface:      prompts/ directory layout
Shared by:    controller prompts_root ↔ gui/main_window._prompts_root ↔ CWD for editable install
Failure mode: PersonaNotFoundError at runtime; duplicate helpers drift (parent.parent vs parent.parent.parent)
Confirmed:    yes — not one shared helper
```

```
Surface:      speech_stack_signature(whisper_language, kokoro_lang_code)
Shared by:    heckler/locale.py ↔ PipelineController reload / hot-swap
Failure mode: Wrong-language STT/TTS after persona/locale change without reload
Confirmed:    yes — kokoro_voice not in signature (voice-only change intentional)
```

```
Surface:      Dual config snapshot (load-time vs session-time)
Shared by:    load_models(target_speech_config) for Transcriber/Speaker ↔ start() apply_persona_overrides for workers/logger/reactor
Failure mode: Gates/prompts use session config; Whisper/Kokoro use load-time config — mismatch if conflated
Confirmed:    yes — controller.py
```

```
Surface:      HeckleEvent field names ↔ event_store columns ↔ migration json_extract
Shared by:    heckler/models.serialize_heckle_event ↔ event_store._EVENT_ANALYTICS_COLUMNS ↔ scripts/import_legacy_jsonl.py
Failure mode: Analytics/import drift on rename
Confirmed:    yes — import script imports private _EVENT_ANALYTICS_COLUMNS, _heckle_event_analytics_params
```

```
Surface:      DiscardReason string values in SQLite
Shared by:    models.DiscardReason ↔ events.discard_reason TEXT ↔ external SQL
Failure mode: Enum rename breaks filters/exports; no migration layer
Confirmed:    yes
```

```
Surface:      LLM JSON keys comment, score, type
Shared by:    reactor._parse_response ↔ prompts/*/system.md ↔ prompts/*/examples.json few-shot shape
Failure mode: Parse failures / bad few-shots
Confirmed:    yes
```

```
Surface:      persona.toml keys ↔ HecklerConfig via _TOML_TO_CONFIG
Shared by:    heckler/persona.py ↔ heckler/config.py
Failure mode: Overrides silently ignored; unknown keys may warn
Confirmed:    yes
```

```
Surface:      HECKLER_* / SCORE_THRESHOLD / PACING_INTERVAL env names
Shared by:    .env ↔ load_config() only
Failure mode: Config not applied if renamed in one place; HECKLER_MODE not validated at load (invalid env stored until start())
Confirmed:    yes — see open-questions.md HECKLER_MODE validation
```

```
Surface:      threading thread names + stop() join order
Shared by:    heckler-transcription, heckler-reaction, heckler-transcribe, heckler-audio-capture ↔ controller.stop()
Failure mode: Hung threads if join/sentinel order changes
Confirmed:    yes
```

```
Surface:      tracing_context thread-local
Shared by:    reactor.react ↔ HecklerLogger.log_event (same reaction thread)
Failure mode: Wrong/missing correlation_json if logging moves threads
Confirmed:    yes
```

```
Surface:      LLM response JSON schema (system prompt)
Shared by:    prompts/*/system.md ↔ heckler/reactor.py ↔ CommentType
Failure mode: LLM_ERROR on schema drift
Confirmed:    yes
```

```
Surface:      HeckleEvent audio_chunk serialization exclusion
Shared by:    serialize_heckle_event ↔ logger
Failure mode: JSON TypeError on numpy if strip omitted
Confirmed:    yes
```

```
Surface:      heckler_schema_version / transcript_schema_version
Shared by:    event_store ↔ transcript_store ↔ one DB file
Failure mode: RuntimeError; transcript side has no upgrade path yet
Confirmed:    yes
```

```
Surface:      Pre-LLM vs post-LLM pacing / on_reaction / analytics
Shared by:    pipeline._run_reaction_worker ↔ GUI on_reaction
Failure mode: Same PACING_GATE enum, different row shape; pre-LLM invisible in reaction feed
Confirmed:    yes
```

```
Surface:      Queue None sentinel + drop-oldest
Shared by:    all _run_*_worker ↔ controller.stop
Failure mode: Hang or partial shutdown
Confirmed:    yes
```

```
Surface:      prompts/ packaging non-editable install
Shared by:    pyproject.toml include heckler* only ↔ README
Failure mode: PersonaNotFoundError without editable clone
Confirmed:    yes
```

```
Surface:      passed_pacing_gate=None semantics
Shared by:    HeckleEvent ↔ SQL analytics
Failure mode: None ("not evaluated") confused with False ("failed")
Confirmed:    suspected — easy misread in dashboards
```

```
Surface:      GUI _LOCALE_DISPLAY / _VOICE_PREFIXES_BY_LANG
Shared by:    gui/main_window.py ↔ locale.SUPPORTED_LOCALES
Failure mode: Locale added in one place only — combo/labels drift
Confirmed:    suspected
```

```
Surface:      Transcriber.run(in_queue, out_queue)
Shared by:    transcriber.py ↔ tests only
Failure mode: Dead alternate worker API if wired by mistake
Confirmed:    suspected — production uses transcribe(chunk) only
```
