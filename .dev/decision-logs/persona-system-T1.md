# persona-system — T1 — Persona module (`heckler/persona.py`)

## Chosen approach

- **`Persona` dataclass** (`name`, `description`, `system_prompt`, `examples`, `config_overrides`) with **`PersonaNotFoundError(ValueError)`** for missing persona directory, missing **`persona.toml`**, or missing required **`system.md`** (bundle incomplete).
- **`load_persona(persona_dir)`** reads **`persona.toml`** via stdlib **`tomllib`**, **`[persona]`** metadata (non-empty **`name`** string; **`description`** optional string, default empty), required sibling **`system.md`**, optional **`examples.json`** (absent → empty list; must be a JSON array of objects when present). **`logger.info("Loaded persona %r from %s", ...)`** after successful load.
- **`config_overrides`** flattened only from **`[voice]`**, **`[llm]`**, **`[gates]`**, **`[output]`**; known keys use the §2 **TOML → `HecklerConfig` field** mapping (e.g. **`pacing_interval` → `min_output_interval_s`**, **`model` → `llm_model`**). **`[output].comment_types`** is skipped (informational-only per plan). Unmapped keys inside those sections keep **TOML-local names** for passthrough; **`apply_persona_overrides`** applies only names that exist on **`HecklerConfig`** and **`logger.warning`**s for unknown keys. **`dataclasses.replace(base, **valid_overrides)`** for the merge.
- **`list_personas(prompts_root)`** returns sorted subdirectory names that contain **`persona.toml`**; missing **`prompts_root`** → empty list.

## Alternatives rejected

- **Raising `PersonaNotFoundError` only for missing dir / `persona.toml` and using raw `FileNotFoundError` for missing `system.md`:** rejected — operators get one **`PersonaNotFoundError`** surface for “bundle not loadable” at startup (pipeline can still catch **`ValueError`** superclass).
- **Embedding `comment_types` in `config_overrides`:** rejected — would spam **WARNING** logs on **`apply_persona_overrides`** for a key that is explicitly informational-only in §2.

## Assumptions made

- **`persona.toml`** declares identity under **`[persona]`** with at least **`name`** (non-empty string after strip). Malformed tables / types raise **`ValueError`** (distinct from not-found).
- **Python ≥ 3.11** ( **`tomllib`** ) per **`pyproject.toml`** **`requires-python`**.
- **`examples.json`** entries are consumed downstream as **`list[dict[str, Any]]`**; **`load_persona`** validates top-level JSON type is **`list`** but does not require each element to be a **`dict`** (callers / T3+ remain responsible).

## Items deferred

- **Strict per-element validation of `examples.json` (every item is a `dict` with expected keys):** deferred — not required by §2 for T1; falsifier would duplicate reactor contract tests.
- **`list_personas` when `prompts_root` exists but is not a directory (e.g. a file path):** deferred — returns **`[]`** today; no test falsifier requested in packet.

## Files added

- **`tests/test_persona.py`** — public API, mapping table / **`dataclasses.replace`** kill-criterion guard, logging smoke, **`tomllib.TOMLDecodeError`** path.
