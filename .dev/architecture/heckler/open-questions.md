Section:      open-questions
Version:      1.2.0
Last updated: 2026-05-24

Architectural forks — not implementation TODOs. Resolved forks move to changelog + relevant decision logs.

```
Question:     Should pipeline._run_*_worker functions become a formal public API?
Impact:       heckler/pipeline.py, heckler/controller.py, tests/, public-interface-inventory.md
Closes when:  Keep private (recommended) OR add heckler/workers.py with documented queue/sentinel contracts and re-export from controller — not merely dropping underscore.
Note:         PipelineController + ControllerCallbacks remain the recommended public seam.
```

```
Question:     Analytics SSOT: normalized SQLite columns vs payload_json dual-write?
Impact:       event_store.py, logger.py, scripts/import_legacy_jsonl.py, analytics
Closes when:  Decision + migration: stop dual-write or declare normalized columns authoritative (code still notes legacy JSON until later subtask).
```

```
Question:     heckler_eval_labels writer ownership?
Impact:       event_store DDL, .dev/eval-strategy.md, future eval tooling
Closes when:  Public insert_eval_label or script-only writer + tests; disambiguate from cooldown_remaining_at_eval.
```

```
Question:     TTS failure taxonomy: synthesis vs playback?
Impact:       speaker.py, pipeline._run_reaction_worker, failure-taxonomy.md
Closes when:  Policy for sd.play failures (map to TTS_ERROR vs propagate); pipeline integration test for TTS_ERROR (today synthesis covered in test_speaker.py only).
```

```
Question:     Split LLM_ERROR (API vs parse) in DiscardReason and analytics?
Impact:       models.py, reactor.py, dashboards, tests
Closes when:  New enum value(s) + migration/backfill rules.
```

```
Question:     Transcriber.run dead API?
Impact:       transcriber.py, tests
Closes when:  Remove or wire as alternate orchestration path.
```

```
Question:     Validate HECKLER_MODE at load_config?
Impact:       config.py, CLI, GUI
Closes when:  Validate persona/transcribe at load OR document intentional passthrough until start() ValueError.
Note:         load_config() currently stores any non-empty HECKLER_MODE string.
```

```
Question:     CPU / non-CUDA Whisper device path?
Impact:       transcriber.py (device="cuda" hardcoded), CI, README
Closes when:  Configurable device + CI story for non-GPU dev.
```

```
Question:     Packaging prompts/ for non-editable pip install?
Impact:       pyproject.toml, persona.py, README
Closes when:  package-data or documented editable-only contract.
```

```
Question:     SQLite Connection.close() lifecycle on shutdown?
Impact:       logger.py, controller.py
Closes when:  Explicit owner + test (deferred since T14).
```

```
Question:     Should pre-LLM pacing honor score_override_threshold?
Impact:       pacing_gate.py, pipeline.py
Closes when:  Document by-design (override post-react only) OR add pre-LLM override API.
Note:         Not a bug today.
```

```
Question:     GUI observability vs SQLite-only history?
Impact:       gui/main_window.py, logger, gui_thougths.md
Closes when:  Product choice: in-app log/feed backend vs DB-only analytics.
```

**Deferrals (not open questions):**

- CI job for architectural-pattern grep falsifiers.
- Per-class failure-taxonomy golden-eval links.
- External-service SLOs / retry policy (no retries at LLM/TTS seams today).
