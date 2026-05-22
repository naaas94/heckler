# Decision log — persona-speech-reload T2: Controller reload API

**Date:** 2026-05-22  
**Subtask:** T2 (persona-speech-reload plan)  
**Supersedes:** locale-lang-propagation-T4.md ("swap never rebuilds")

## Decision: Conditional reload based on speech-stack signature

Landed: `PipelineController.swap_persona` is now a pure same-signature Reactor hot-swap. Cross-locale dispatch lives in `HecklerMainWindow._apply_persona_and_speech`. The reload predicate compares `(whisper_language, kokoro_lang_code)` tuples — no per-persona lookup table.

## Alternatives rejected

**A. Put full dispatch (including ask dialog) inside `swap_persona`.**  
Rejected: controller has no GUI callback for dialog or combo revert; threading model requires dialog on GUI thread; cross-layer coupling unacceptable.

**B. Reload predicate keyed on persona name.**  
Rejected: per-persona dict would drift from SUPPORTED_LOCALES; signature-based predicate is self-consistent and handles locale overrides uniformly (D1).

## Assumptions

- `HecklerConfig` is immutable enough for `dataclasses.replace()` to be safe.
- `loaded_speech_stack()` reading `self._transcriber._config` is safe since `_transcriber` is set by `load_models` and not mutated afterward.

## Deferred

- Voice-only change (same locale) does not trigger reload (G14, spec §12).
