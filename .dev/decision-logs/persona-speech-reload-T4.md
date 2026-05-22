# Decision log — persona-speech-reload T4: ModelLoadThread ownership

**Date:** 2026-05-22  
**Subtask:** T4 (persona-speech-reload plan)

## Chosen approach

- **`ModelLoadThread`** stores **`mode: str`** plus **`persona_name_fn`** and **`locale_override_fn`** callables; **`run()`** invokes them immediately before **`load_models(..., persona_name=..., locale_override=...)`**.
- **`app.main()`** passes **`window.selected_persona_name`** and **`window.selected_locale_override`** so startup load reflects the live combo, not **`HecklerConfig.persona_name`** frozen at thread construction.
- **`HecklerMainWindow.selected_persona_name()`** exposes combo text; **`_apply_models_ready`** enables the persona combo when models are ready and persona mode is selected (no **`is_running`** gate).
- **Start (persona):** **`ensure_heavy_models`** (auto, no dialog) runs on the GUI thread before **`controller.start()`**; T5 will wrap this in **`_apply_persona_and_speech`**.

## Alternatives rejected

- **Store `HecklerMainWindow` on the thread:** rejected — circular-import risk and tight coupling; callables keep **`app.py`** independent of window type.
- **Snapshot persona/locale strings at `ModelLoadThread.__init__`:** rejected — user can change the combo between construction and **`run()`**; at-run-time read is the only safe contract (D7 covers post-load races separately).
- **Offload Start-path `ensure_heavy_models` to a QThread in T4:** rejected — same blocking semantics as before; T5 owns reload UX and threaded offload.

## Assumptions made

- **`app.main()`** keeps the window alive until **`ModelLoadThread`** finishes ( **`loader.failed` → `app.quit()`** ).
- T3 **`selected_locale_override()`** is landed; T2 **`ensure_heavy_models`** / **`load_models(locale_override=...)`** are landed.
- T5 will replace the inline Start **`ensure_heavy_models`** block without double-calling ensure (see plan §5.4 coupling 5).

## Items deferred

- **Ask dialog / `_apply_persona_and_speech`:** T5.
- **Reload speech button and `_reloading` mutex UX:** T5 ( **`_reloading`** gate in **`_apply_models_ready`** is reserved for T5).
- **End-to-end test that Spanish persona TOML changes Whisper at GUI startup:** controller bake tests cover merge; GUI tests assert callables and kwargs only (same deferral as locale-lang-propagation T7).
