Section:      architectural-patterns
Version:      1.2.0
Last updated: 2026-05-24

Observed conventions from code and tests (merged Phase 8 + independent code-only pass). Most enforcement is tests + review, not CI grep.

```
Pattern:      frozen_heckler_config_load_config
Description:  Single frozen HecklerConfig; env via load_config() (HECKLER_* strip/empty→default); persona merge via apply_persona_overrides + apply_resolved_locale. os.environ reads should stay in config.py / reactor observability probes only.
Falsifier:    rg "os.environ\[" heckler/ outside config.py; tests/test_config.py, tests/test_models.py
```

```
Pattern:      react_never_raises_for_llm_failure
Description:  Reactor.react returns (Optional[ReactorResult], float, Optional[DiscardReason]); API/parse → LLM_ERROR; score → SCORE_GATE. Pipeline handles result is None; no raise on normal LLM failure path.
Falsifier:    rg "raise" inside reactor.react try around litellm.completion; tests/test_reactor.py (test_api_exception_returns_none_no_raise, parse/score tests)
```

```
Pattern:      structured_pipeline_outcomes
Description:  Workers build HeckleEvent + heckler_logger.log_event; tri-state passed_*_gate semantics documented on dataclass.
Falsifier:    rg log_event without HeckleEvent; tests/test_pipeline.py, tests/test_controller.py field semantics
```

```
Pattern:      gate_ordering_persona_mode
Description:  Transcription → density (passes_gate) → reaction worker → pre-LLM cooldown_status → react → post-LLM evaluate → _execute_spoken_reply.
Falsifier:    Read _run_transcription_worker / _run_reaction_worker in pipeline.py; test_reaction_worker_pre_llm_pacing_skips_react, test_execute_spoken_reply_records_before_speak
```

```
Pattern:      score_gate_strict_less_than
Description:  Score gate uses parsed.score < config.score_threshold — at-threshold passes (0.65 passes when threshold is 0.65).
Falsifier:    <= in reactor.py score check; tests/test_reactor.py::test_score_at_exact_threshold_passes
```

```
Pattern:      bounded_queues_drop_oldest
Description:  _put_drop_oldest in audio_capture.py; used from capture emit and pipeline workers on full bounded queues.
Falsifier:    Second overflow policy implementation; tests/test_audio_capture.py::test_emit_on_full_queue_drops_oldest_chunk, test_put_drop_oldest_*
```

```
Pattern:      shutdown_none_sentinel_ordered_joins
Description:  Workers break on item is None; persona stop: join transcription, then reaction sentinel, then join reaction (120s). Thread names heckler-transcription, heckler-reaction, heckler-transcribe, heckler-audio-capture.
Falsifier:    controller.stop() ordering vs worker break; test_put_shutdown_sentinel_drops_oldest_when_queue_full; test_main_shutdown_stops_capture_and_joins_threads
```

```
Pattern:      tts_pacing_coupling_surface_6
Description:  record_output() immediately before speaker.speak(), only via _execute_spoken_reply (docstring: coupling surface 6).
Falsifier:    rg speak( before record_output in pipeline; test_execute_spoken_reply_records_before_speak
```

```
Pattern:      mic_gate_during_playback
Description:  Shared threading.Event is_playing; set before synthesis, clear after play + optional tts_gate_tail_ms. Persona mode wires Speaker before AudioCapture.
Falsifier:    AudioCapture without speaker event in persona mode; tests/test_speaker.py, tests/test_audio_capture.py::test_emit_skips_when_speaker_is_playing
```

```
Pattern:      capture_16khz_playback_24khz
Description:  sample_rate 16000 for Silero/Whisper; Kokoro played at 24000. Capture loop raises ValueError if sample_rate != 16000.
Falsifier:    rg sample_rate|16000|24000 heckler; audio_capture ValueError message
```

```
Pattern:      pipeline_controller_threading_hot_swap
Description:  PipelineController owns threads; ReactorHolder lock for persona swap; workers catch broad Exception, log, continue.
Falsifier:    swap_persona without holder; missing join ordering in stop(); tests/test_reactor_holder_swap_*, test_main_shutdown_stops_capture_and_joins_threads
```

```
Pattern:      worker_threads_swallow_and_continue
Description:  _run_*_worker outer except Exception: logger.exception(...) — thread does not exit on one bad item.
Falsifier:    Missing outer handler on new worker code [aspiration — falsifier pending: no dedicated linter]
```

```
Pattern:      ui_callbacks_must_not_kill_workers
Description:  on_transcript / on_reaction wrapped in try/except + logger.exception in pipeline workers.
Falsifier:    rg on_reaction|on_transcript heckler/pipeline.py without surrounding try; tests/test_controller.py
```

```
Pattern:      sqlite_dual_write_ssot
Description:  HecklerLogger → insert_heckle_event_row (payload_json + normalized columns + optional event_reactor_results); WAL pragmas in open_store.
Falsifier:    Direct INSERT INTO events outside event_store; tests/test_event_store.py, tests/test_context_buffer_and_logger.py
```

```
Pattern:      persona_bundles_on_disk
Description:  prompts/<id>/persona.toml, system.md, optional examples.json; _TOML_TO_CONFIG mapping; load via load_persona / controller prompts_root.
Falsifier:    Hardcoded prompt paths outside load_persona; tests/test_persona.py, tests/test_persona_prompt_bundle.py
```

```
Pattern:      persona_io_at_boundaries_only
Description:  Reactor receives system_prompt + examples at construct time — no filesystem reads inside reactor.py.
Falsifier:    rg open|read_text|load_persona heckler/reactor.py — expect empty
```

```
Pattern:      stdlib_logging_per_module
Description:  logging.getLogger(__name__) per module; CLI/GUI use callbacks/print for operator-visible lines.
Falsifier:    Ad-hoc logging frameworks in heckler/
```

```
Pattern:      correlation_hygiene
Description:  clear_correlation() before litellm.completion; set from response; clear_correlation() in HecklerLogger.log_event finally (same reaction thread).
Falsifier:    rg clear_correlation / set_correlation pairing; logging HeckleEvent from another thread without set [aspiration — falsifier pending: integration test]
```

```
Pattern:      context_buffer_all_terminal_paths
Description:  After density pass, reaction worker context_buffer.push(transcript) on reject and success, including pre-LLM pacing.
Falsifier:    New continue in _run_reaction_worker without push; pacing tests assert push
```

```
Pattern:      on_reaction_requires_reactor_result
Description:  No on_reaction on pre-LLM pacing, LLM_ERROR, SCORE_GATE; fires with was_spoken=False on post-LLM pacing/TTS path; True only when spoken.
Falsifier:    tests/test_controller.py callback matrix
```

```
Pattern:      gui_thread_boundary
Description:  Worker callbacks go through SignalBridge (pyqtSignal), not direct Qt widget mutation.
Falsifier:    Callbacks touching widgets without emit; tests/test_gui.py (partial)
```

```
Pattern:      import_cycle_control
Description:  controller imports pipeline _run_* at import time; pipeline → controller only TYPE_CHECKING + lazy import in main(). Architecturally mutual — pipeline is not free of controller semantics.
Falsifier:    New mutual top-level imports; python -c "import heckler.pipeline"
```

```
Pattern:      private_workers_by_convention
Description:  _run_*_worker imported by controller.py and tests — no __all__, no stable public worker API. Promote via heckler/workers.py with documented contracts if needed, not merely dropping underscore.
Falsifier:    New external package importing _run_* without test updates
```

**Honest gap:** Most conventions lack automated CI grep rules; drop-oldest, record-before-speak, react tuple, score-at-threshold, and JSON round-trip have direct test falsifiers today.
