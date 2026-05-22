# locale-lang-propagation — T1 — unified locale knob (config + resolver)

## Chosen approach

- **`heckler/locale.py`** owns **`SUPPORTED_LOCALES`**, **`normalize_locale`**, **`resolve_locale`**, and **`UnsupportedLocaleError`**.
- **`HecklerConfig`** gains **`locale`** (operator slug) and **`kokoro_lang_code`**; **`whisper_language`** remains on the dataclass but is **derived** via **`apply_resolved_locale`** (not read from env in v1).
- **`load_config()`** reads **`HECKLER_LOCALE`** with strip / whitespace-only → **`"en"`**, then returns **`apply_resolved_locale(cfg)`** so STT/TTS fields align before any consumer runs.
- Initial keys: **`en`**, **`en-us`**, **`en-gb`**, **`es`** → Whisper **`en`/`es`** and Kokoro **`a`/`b`/`e`** per plan §2.

## Alternatives rejected

- **Split env knobs (`WHISPER_LANGUAGE` + `KOKORO_LANG`):** rejected — violates unified-knob resolution (context-map Flag 1); reintroduces ISO vs letter vocabulary collision.
- **Silent fallback to English on unknown locale:** rejected — operators must get **`UnsupportedLocaleError`** at config construction (kill criterion 4).

## Assumptions made

- **Kokoro voice selection stays operator-owned:** `kokoro_voice` is unchanged; Spanish locale (`es` → `e`) does not imply a valid Spanish voice id — operators must pick a voice compatible with the resolved **`kokoro_lang_code`** (T2 wires **`Speaker`**).
- **Flag 1 / Flag 4 resolved at plan §0:** mapping table + **`HECKLER_LOCALE`** wiring are sufficient for T1; persona **`[voice].locale`** and controller **`load_models`** binding are **T3/T4**.

## Items deferred

- **`Speaker` / `controller.py` wiring:** T2/T4 — not in T1 **Files to touch**.
- **Persona `[voice].locale` → `apply_persona_overrides`:** T3.
- **README / operator docs for supported locales:** T5.
- **Adversarial gap:** no test that a stray **`WHISPER_LANGUAGE`** env var is ignored — v1 contract is env-absent only; operators must use **`HECKLER_LOCALE`**.

## Files added

- **`heckler/locale.py`**
- **`tests/test_locale.py`**
