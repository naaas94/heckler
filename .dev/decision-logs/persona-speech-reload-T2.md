# persona-speech-reload — T2 — controller reload API

## Chosen approach

- **`SpeechReloadPolicy`** enum (`auto` / `ask` / `never`) on **`PipelineController`** for T5 GUI policy wiring.
- **`target_speech_config`** is the single derive path for persona merge, optional **`locale_override`** (falsy = from persona), and base locale resolution; **`load_models`**, **`heavy_models_need_reload`**, and **`ensure_heavy_models`** all use it.
- **`loaded_speech_stack`** returns **`speech_stack_signature`** from the loaded transcriber config, or **`None`** if no transcriber.
- **`reload_speech_stack_for_persona`** tracks **`was_running`** before **`stop()`** and only **`start("persona", ...)`** if the pipeline was running.
- **`switch_mode`** to **`persona`** calls **`ensure_heavy_models`** after **`stop()`** so transcribe → persona gets a Speaker.
- **`swap_persona`** docstring updated to same-signature Reactor hot-swap only; cross-locale dispatch deferred to T5 **`_apply_persona_and_speech`**.
- Removed **`_heavy_model_config`** (only caller was **`load_models`**).

## Alternatives rejected

- **Rebuild Transcriber/Speaker inside `swap_persona`:** rejected — controller stays GUI-agnostic; ask/revert policy belongs in T5 view layer (plan §5.1 Alternative A).
- **Keep `_heavy_model_config` as alias to `target_speech_config`:** rejected — duplicate surface; grep showed no other callers.

## Assumptions made

- **T1 landed:** **`speech_stack_signature`** and **`supported_locale_labels`** exist in **`heckler.locale`**.
- **Lazy imports inside methods** avoid circular import between **`controller`** and **`locale`**.
- **`locale_override=""`** is treated like **`None`** via **`if locale_override:`** (never passed to **`resolve_locale`** as empty).

## Items deferred

- **GUI ask/auto dispatch and QThread offload for reload:** T5 owns **`_apply_persona_and_speech`** and blocking reload UX.
- **CLI `ensure_heavy_models` before start:** T6.
- **Replace `test_swap_persona_does_not_change_transcriber_whisper_language`:** T7 scenario matrix.
- **Adversarial gap:** no test that **`load_models`** propagates model-load **`Exception`** through **`ensure_heavy_models`** / **`reload_speech_stack_for_persona`** without swallowing — callers must not catch per contract; verified by code review only.
