Section:      failure-taxonomy
Version:      1.2.0
Last updated: 2026-05-24

Taxonomy version: 1.2.0
Last updated:     2026-05-24

## Layer framework

Labels are **not defined in code**; they describe pipeline topology and `DiscardReason` usage.

```
L0  Input integrity   — capture constraints, segment shape, locale/persona bootstrap input
L2  Model behavior    — STT model output (Whisper) relative to audio input
L3  Output validation — LLM response structure, parse, score gate, reactor contract
L5  Infrastructure    — persistence, devices, threads, optional hosted traces
Lg  Gate rejection    — expected discard by density, score, pacing (not necessarily errors)
Bootstrap           — startup/config errors before steady-state pipeline (persona, locale, pipeline state)
```

**Mapping notes:** Same `DiscardReason` can imply different `HeckleEvent` row shapes (pre-LLM vs post-LLM pacing). `LLM_ERROR` collapses API and parse in the enum. Unrecognized LLM `type` → `CommentType.UNKNOWN` is **not** a failure class — commentary can still speak if score passes.

## Cause classes

```
Lg.density_gate
One-line: passes_gate fails (min_word_count / density_threshold); default no row; optional log_density_failures → DENSITY_GATE.
Evidence: DiscardReason.DENSITY_GATE; tests/test_semantic_gate.py; LOG_DENSITY_FAILURES in tests/test_models.py only (pipeline persist path weakly tested)
```

```
Lg.density_reject_unlogged
One-line: Density fail with log_density_failures=False — no HeckleEvent, not enqueued to reaction.
Evidence: pipeline transcription worker; HecklerConfig.log_density_failures
```

```
Lg.score_gate
One-line: reactor.react returns SCORE_GATE when score < score_threshold (at-threshold passes).
Evidence: DiscardReason.SCORE_GATE; tests/test_reactor.py::test_score_at_exact_threshold_passes, tests/test_pipeline.py
```

```
Lg.pacing_gate_pre_llm
One-line: cooldown_status() true before react() — PACING_GATE, no reactor_result, on_reaction not called.
Evidence: tests/test_pipeline.py pre-LLM pacing tests; pacing-before-llm decision log
```

```
Lg.pacing_gate_post_llm
One-line: evaluate(score) false after successful react() — PACING_GATE with full reactor payload; on_reaction(result, False).
Evidence: tests/test_controller.py; same enum, different row shape
```

```
L3.llm_api_error
One-line: litellm.completion exception → (None, latency, LLM_ERROR).
Evidence: tests/test_reactor.py::test_api_exception_returns_none_no_raise
Note: Stored as DiscardReason.LLM_ERROR — enum split deferred (open-questions.md).
```

```
L3.llm_parse_error
One-line: Invalid JSON, missing keys, empty choices → LLM_ERROR (same enum as API).
Evidence: tests/test_reactor.py parse failures
Note: Taxonomy distinguishes; DB enum does not.
```

```
L3.reactor_contract_violation
One-line: react() returns (None, latency, None) — pipeline logs ERROR, coerces to LLM_ERROR.
Evidence: test_reaction_worker_react_none_discard_none in tests/test_pipeline.py
```

```
L5.tts_synthesis_error
One-line: SpeakerError from synthesis — pipeline logs TTS_ERROR, spoken=False.
Evidence: pipeline path in _run_reaction_worker; tests/test_speaker.py (synthesis). **No test in tests/test_pipeline.py asserts TTS_ERROR.**
```

```
L5.tts_playback_failure
One-line: sd.play raises OSError (etc.); is_playing cleared in finally; not SpeakerError/TTS_ERROR — propagates out of speak().
Evidence: tests/test_speaker.py::test_play_failure_still_clears_event, test_play_failure_skips_post_playback_tail_sleep
Note: Policy fork in open-questions.md.
```

```
Bootstrap.persona_bundle_failure
One-line: PersonaNotFoundError, bad TOML or examples.json → startup/GUI errors.
Evidence: tests/test_persona.py, tests/test_persona_prompt_bundle.py
```

```
Bootstrap.unsupported_locale
One-line: UnsupportedLocaleError at resolve_locale / persona merge.
Evidence: tests/test_config.py, tests/test_persona.py
```

```
Bootstrap.pipeline_state_error
One-line: PipelineAlreadyRunningError, PipelineNotRunningError, unknown mode ValueError.
Evidence: heckler/controller.py
```

```
L0.capture_sample_rate_mismatch
One-line: sample_rate != 16000 when capture loop starts → ValueError.
Evidence: audio_capture.py "HECKLER requires sample_rate=16000..."
```

```
L0.silero_hub_layout_mismatch
One-line: Unexpected torch.hub.load utils tuple length → RuntimeError at capture start.
Evidence: audio_capture VAD init
```

```
L0.audio_chunk_invalid
One-line: Non–float32 1D numpy in _emit_audio_segment → TypeError; worker drops item, no HeckleEvent.
Evidence: audio_capture; worker exception handler
```

```
L2.empty_stt_output
One-line: transcribe returns ""; transcribe worker skips persist; persona path still runs density on "" (typically fails density).
Evidence: transcriber.py; _run_transcribe_worker continue
```

```
L2.whisper_load_failure
One-line: Transcriber.__init__ logs and re-raises; device="cuda" hardcoded.
Evidence: transcriber.py
Note: CPU/non-CUDA path is open question (open-questions.md).
```

```
L5.sqlite_heckler_schema_mismatch
One-line: init_schema RuntimeError if stored version > SCHEMA_VERSION or unsupported migration step.
Evidence: tests/test_event_store.py
```

```
L5.sqlite_transcript_schema_mismatch
One-line: init_transcript_schema RuntimeError on version mismatch; no upgrade path yet.
Evidence: transcript_store.py
```

```
L5.sqlite_insert_failure
One-line: HecklerLogger.log_event logs ERROR and re-raises after finally clear_correlation.
Evidence: logger.py
```

```
L5.worker_item_dropped
One-line: Per-item logger.exception in worker — utterance lost, often no DB row.
Evidence: _run_*_worker outer except blocks
```

```
L5.queue_shutdown_hang
One-line: Worker blocked in long react() when sentinel queued — 120s join + warning; no stress test.
Evidence: controller.stop()
```

```
L0.tts_bleed_recursive_heckle
One-line: Prevented failure if is_playing Event wrong — gate + tts_gate_tail_ms.
Evidence: capture-mic-gate audit; coupling surface 2
```

```
L5.gui_callback_exception
One-line: Swallowed in worker; UI may desync — no DB row.
Evidence: pipeline callback wrappers
```

**Anticipated, weakly tested:** CUDA/device missing at Whisper init; sounddevice open failures; DB lock timeout (30s busy_timeout set, no dedicated test).

**Not registered (deliberate):** hosted trace misconfig (silent no-op), eval-label workflow, score-gate near-miss analytics.

**Deferred:** Splitting LLM_ERROR in DiscardReason enum; golden-eval links per class; density-gate persistence integration test when LOG_DENSITY_FAILURES=true.
