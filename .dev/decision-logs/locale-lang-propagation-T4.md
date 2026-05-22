# locale-lang-propagation — T4 — controller load-time locale bake

## Chosen approach

- **`PipelineController.load_models`** accepts optional keyword-only **`persona_name`**; heavy models construct from **`_heavy_model_config(persona_name)`** — persona path uses **`apply_persona_overrides(self._config, load_persona(...))`**, else **`apply_resolved_locale(self._config)`**.
- **`swap_persona`** docstring documents STT/TTS locale is load-time fixed; implementation unchanged (Reactor-only hot-swap).
- **`tests/test_controller.py`** captures configs passed to **`Transcriber`/`Speaker`** at load and asserts **`swap_persona`** does not mutate **`Transcriber._config.whisper_language`**.

## Alternatives rejected

- **Rebuild Transcriber/Speaker inside `swap_persona`:** rejected — plan Flag 2 / gui-T1 heavy-model ownership; expensive and racy on live mic.
- **Bake persona locale only in `_start_persona_mode`:** rejected — leaves Surface 1 (merged worker `cfg` vs English Transcriber) when GUI calls **`load_models()`** before persona pick without reload.

## Assumptions made

- **T1/T3 landed:** **`apply_resolved_locale`** and persona **`[voice].locale`** mapping exist and are tested elsewhere.
- **GUI/CLI call order:** operators who change persona locale for STT/TTS must call **`load_models(persona_name=...)`** again (or restart); runtime **`swap_persona`** alone updates LLM/gates only — documented in **`load_models`** / **`swap_persona`** docstrings until a future plan adds reload UX.

## Items deferred

- **Automated GUI reload after persona pick:** out of scope (T5 docs may note); no **`heckler/gui/**`** edits in T4.
- **Adversarial gap:** no test that a second **`load_models(persona_name=...)`** replaces an already-loaded transcriber with a new locale — reload API is implicit; operators rely on explicit reload call.
