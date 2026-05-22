> **SUPERSEDED** by `persona-speech-reload` plan (2026-05-22).
> Decision: `ModelLoadThread` now uses callable snapshots read at `run()` time instead of `config.persona_name` at init.
> See `.dev/decision-logs/persona-speech-reload-T4.md` for the landed behavior.
> The "ModelLoadThread passes config.persona_name" statement below describes pre-T4 behavior only.

# locale-lang-propagation — T7 — GUI ModelLoadThread persona at load

## Chosen approach

- **`ModelLoadThread`** stores **`HecklerConfig`**; **`run()`** calls **`load_models(on_progress=..., mode=..., persona_name=...)`** with **`mode = (config.mode or "persona").strip().lower()`** and **`persona_name = config.persona_name`** only when **`mode == "persona"`**, else **`None`**.
- **`main()`** passes **`load_config()`** result into **`ModelLoadThread(controller, config)`** so startup heavy models match **`PipelineController.load_models(persona_name=...)`** contract (FIND-05).

## Alternatives rejected

- **Locale picker / reload on persona-combo change while running:** rejected — plan non-goals; Flag 2 unchanged (**`swap_persona`** stays Reactor-only).
- **Pass only `persona_name` without `mode`:** rejected — transcribe GUI would still load Speaker via default **`load_models()`**; **`mode=config.mode`** aligns with CLI T6 pattern.

## Assumptions made

- **Pre-start persona:** persona combo is disabled until models ready; **`_populate_personas`** selects **`config.persona_name`**, so startup **`persona_name`** matches first **`start(persona_name=combo)`** when the user does not change the combo before Start.
- **T4 API landed:** **`load_models(..., persona_name=...)`** bakes persona **`[voice].locale`** into Transcriber/Speaker at load.

## Items deferred

- **Persona hot-swap STT/TTS reload:** changing persona combo while running does not call **`load_models`** again — documented in T4/T5; no GUI reload UX in T7.
- **Adversarial gap:** no integration test that a persona TOML with **`locale=es`** actually yields Spanish Whisper at GUI startup (controller bake covered in **`test_controller.py`**; GUI test asserts kwargs only).
