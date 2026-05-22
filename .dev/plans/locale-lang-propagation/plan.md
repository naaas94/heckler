# Plan — locale-lang-propagation

**Version:** 1.2.0  
**Plan name:** `locale-lang-propagation`  
**Skill:** orchestrator-planning v0.6  
**Date:** 2026-05-22  
**Status:** Complete (v1.2.0 — amendment landed 2026-05-22)

---

## §0 Context map intake

- **Path consumed:** `.dev/plans/locale-lang-propagation/context-map.md` (promoted from `.dev/plans/_pending/locale-lang-propagation/`)
- **Readiness verdict:** CONDITIONAL
- **Scope-area labels flagged:** Flag 1 (`STT-TTS-unified-knob`), Flag 2 (`persona-hot-swap`), Flag 3 (`LLM-alignment`), Flag 4 (`config-env-STT`)
- **Skill version + commit SHA:** pre-plan-exploration v0.2 @ `56c3748e99ea84bb6fa398bbaf474e0508918a99` (map); planning-time `HEAD` = `692dfa0c9a398544b611d1d59b7609f8e0609261` — **stale vs map**; reconcile touched files against current tree at execution.

**Binding-artifact note:** Plan bundle (context-map, plan, packets) is **not yet tracked** at planning SHA; **T5** commits `.dev/plans/locale-lang-propagation/` so §8.2 can resolve. `.dev/decision-logs/persona-system-T1.md` and `gui-T1.md` are tracked and authoritative for persona flattening and heavy-model ownership.

**Operator resolutions applied before planning** (from context-map §Orchestrator handoff notes):

- **Flag 1 (unified knob):** Resolved. Single product field `HecklerConfig.locale` (BCP-47-ish slug, normalized lowercase) maps via `heckler/locale.py` to Whisper ISO 639-1 `whisper_language` and Kokoro single-letter `kokoro_lang_code`. Mapping table + unit tests are **T1** contract anchors; no raw Kokoro letter passed through env/persona.
- **Flag 2 (persona hot-swap):** Resolved. `swap_persona` does **not** rebuild `Transcriber`/`Speaker` or change STT/TTS language; document and test. Persona `[voice].locale` affects STT/TTS only when baked into heavy models at `load_models(..., persona_name=...)` (or process env before load). **T4** owns controller semantics.
- **Flag 3 (LLM register):** Resolved as **non-goal**. LLM language/register remains `system.md` / `examples.json` only; no `HecklerConfig` LLM-locale field or Reactor template injection in v1.
- **Flag 4 (env wiring):** Resolved. `load_config()` reads `HECKLER_LOCALE` with strip / whitespace fallback like `HECKLER_MODE`; **T1** tests required.

**Supersession / historical:**

- Archive heckler-v1 T8 kill criterion “`lang_code` other than `'a'`” is **historical only** — superseded by this plan’s multilingual Kokoro contract.
- `README.md` L3 “English speech” — **T5** amends operator-facing positioning when multilingual locales ship.

---

## §1 Task statement

Implement a **unified locale knob** on `HecklerConfig` that propagates to faster-whisper (`whisper_language`) and Kokoro (`kokoro_lang_code` on `KPipeline`), with operator entry points via **`HECKLER_LOCALE`** and persona **`[voice].locale`**, plus resolution at config construction so STT and TTS stay aligned. Wire `Speaker` off the hard-coded `lang_code="a"`, close the `load_config()` gap for language env, and fix controller **load-time** binding so `Transcriber`/`Speaker` use the locale effective for the session (including persona merge when `load_models(persona_name=...)` is used). Document that **persona hot-swap does not change STT/TTS language** without a process restart / `load_models` reload.

**Non-goals:**

- New GUI **locale picker** widget or PyQt language controls beyond wiring existing `load_models` / `start` call sites (**T6/T7** amend propagation at entry points; not a picker UI).
- New CLI flags beyond existing `--persona` / `--mode` (amendment wires `--persona` into `load_models`, no new flag strings).
- LLM “locale” field, Reactor template injection, or automatic register alignment beyond existing prompts.
- Rebuilding `Transcriber`/`Speaker` on `swap_persona` or mode switch without explicit `load_models` reload.
- Auto-detect language from audio (Whisper `language=None` “detect” mode).
- Expanding Kokoro beyond locales listed in §2 mapping table without plan amendment.
- Split per-stack knobs (`whisper_language` vs `kokoro_lang_code` as independent user inputs) — internal fields exist; operators set **`locale`** only.

---

## §2 Shared contracts

| Topic | Contract |
|-------|----------|
| **Types / interfaces** | **`heckler/locale.py` (owning subtask: **T1**):** `UnsupportedLocaleError(ValueError)` when normalized locale not in `SUPPORTED_LOCALES`. **`SUPPORTED_LOCALES: dict[str, LocaleProfile]`** frozen mapping (test: `tests/test_locale.py`). **`LocaleProfile`** `NamedTuple` or frozen dataclass: `whisper_language: str`, `kokoro_lang_code: str`. **`normalize_locale(raw: str) -> str`**: strip, lower, reject empty → `UnsupportedLocaleError`. **`resolve_locale(locale: str) -> LocaleProfile`**: normalize then lookup. **Initial supported keys (binding):** `en`, `en-us`, `en-gb`, `es` → profiles: `(en,a)`, `(en,a)`, `(en,b)`, `(es,e)` respectively (Kokoro aliases per hexgrad/kokoro `ALIASES` / `LANG_CODES`). **`heckler/config.py` — `HecklerConfig` (T1):** add `locale: str = "en"`; add `kokoro_lang_code: str = "a"`; retain `whisper_language: str = "en"` as **derived** from locale (not env-direct in v1). **`apply_resolved_locale(cfg: HecklerConfig) -> HecklerConfig` (T1):** `dataclasses.replace(cfg, whisper_language=profile.whisper_language, kokoro_lang_code=profile.kokoro_lang_code)` after `resolve_locale(cfg.locale)`; test: `tests/test_locale.py` + `tests/test_config.py`. **`load_config()` (T1):** read `HECKLER_LOCALE` with strip; whitespace-only → default `"en"`; then `apply_resolved_locale` on returned config; tests mirror `HECKLER_MODE` strip semantics. **`heckler/speaker.py` — `Speaker.__init__` (T2):** `KPipeline(lang_code=config.kokoro_lang_code)`; test: `tests/test_speaker.py` parametrized or updated assertions. **`heckler/transcriber.py` (unchanged signature):** continues `language=self._config.whisper_language`; falsified by existing `tests/test_transcriber.py` once T1 resolves fields. **`heckler/persona.py` (T3):** `_TOML_TO_CONFIG` adds `("voice", "locale") → "locale"`. **`apply_persona_overrides` (T3):** after merge valid fields, return `apply_resolved_locale(replace(...))`. **`PipelineController.load_models` (T4):** add optional keyword-only `persona_name: str | None = None`; when set, construct heavy models from `apply_persona_overrides(self._config, load_persona(...))` (resolved locale), else `apply_resolved_locale(self._config)`; **do not** change `swap_persona` to rebuild transcriber/speaker. **Persona TOML table (T3):** `[voice] locale = "es"` documented in README / persona_builder optional. |
| **Error envelope** | `UnsupportedLocaleError` on unknown/empty locale at `resolve_locale` / `apply_resolved_locale` (fail at config construction, not at first transcribe). `load_config` invalid `TTS_GATE_TAIL_MS` behavior unchanged. No change to `SpeakerError`, `PersonaNotFoundError`. |
| **Naming** | Module `heckler/locale.py`. Env `HECKLER_LOCALE`. Config fields `locale`, `kokoro_lang_code` (retain `whisper_language`). Persona key `[voice].locale`. Decision logs: `.dev/decision-logs/locale-lang-propagation-T1.md`, `.dev/decision-logs/locale-lang-propagation-T4.md`. |
| **Logging** | Optional `logger.info` on `load_models` when persona locale differs from base `self._config.locale` — **out of scope** (YAGNI). No new structured log fields required. |
| **Tests** | **pytest** under `tests/`. v1.0 modules per T1–T5. **Amendment verification (T6–T8):** `pytest tests/test_locale.py tests/test_config.py tests/test_speaker.py tests/test_persona.py tests/test_controller.py tests/test_pipeline.py tests/test_gui.py -q` (no GPU/network). |
| **CLI surface** | N/A — no new argparse flags. Existing `--persona`, `--mode`, `--session-name` unchanged. |
| **Entry-point integration** *(amendment v1.2.0 — **T6**, **T7**)* | **`heckler/pipeline.py` `main()` (T6):** After resolving `persona_name = args.persona or config.persona_name`, call `controller.load_models(..., mode=mode, persona_name=persona_name if mode == "persona" else None)` so heavy models match the persona passed to `start()`. **Falsifier:** `tests/test_pipeline.py` — mock/capture `load_models` kwargs or `Transcriber` config for persona with `[voice].locale = "es"` vs base `en`. **`heckler/gui/app.py` `ModelLoadThread` (T7):** Pass `persona_name=config.persona_name` and `mode=config.mode` into `load_models` when `config.mode == "persona"` (matches combo default from `_populate_personas` before `start()`). **Falsifier:** `tests/test_gui.py` asserts `load_models(..., persona_name=..., mode=...)`. **Out of scope:** Rebuild heavy models on `swap_persona` or persona-combo change while running (Flag 2 unchanged). |

**Decision log paths:**

- T1 (architectural): `.dev/decision-logs/locale-lang-propagation-T1.md`
- T4 (architectural): `.dev/decision-logs/locale-lang-propagation-T4.md`
- T7 (standard): `.dev/decision-logs/locale-lang-propagation-T7.md` *(amendment)*

---

## §3 Dependency DAG

```mermaid
graph LR
    T1["T1: locale module + config + env"]
    T2["T2: Speaker kokoro_lang_code"]
    T3["T3: persona locale mapping"]
    T4["T4: controller load_models persona bake"]
    T5["T5: docs + tracked plan bundle"]
    T6["T6: CLI load_models persona_name"]
    T7["T7: GUI load_models persona_name"]
    T8["T8: plan §8 + audit narrative"]

    T1 --> T2
    T1 --> T3
    T2 --> T4
    T3 --> T4
    T4 --> T5
    T5 --> T6
    T5 --> T7
    T6 --> T8
    T7 --> T8
```

**Parallel groups:** `{T2, T3}` after **T1**; `{T6, T7}` after **T5** (amendment wave).

**Soft dependencies:** None.

---

## §4 Subtask specs

### T1 — Locale resolution module and config/env wiring

| Field | Content |
|-------|---------|
| **ID** | T1 |
| **Scope** | Add `heckler/locale.py` with supported locale table, normalization, and resolution; extend `HecklerConfig` with `locale` + `kokoro_lang_code`; implement `apply_resolved_locale`; wire `HECKLER_LOCALE` in `load_config()`; add `tests/test_locale.py` and config tests. |
| **Files to touch** | `heckler/locale.py` (new), `heckler/config.py`, `tests/test_locale.py` (new), `tests/test_config.py`, `.dev/decision-logs/locale-lang-propagation-T1.md` (new) |
| **Contract bindings** | All §2 rows owned by T1 |
| **Inputs** | None |
| **Outputs** | Locale module, config fields, env wiring, tests, decision log |
| **Kill criteria** | (1) Halt if context-map Flag 1 unresolved at execution start: no mapping table or operators must set `whisper_language` / `kokoro_lang_code` independently via env. (2) Halt if context-map Flag 4 unresolved: `load_config()` omits `HECKLER_LOCALE` or lacks strip/fallback tests. (3) Halt if `Speaker` or `controller.py` edited in this subtask (wrong packet). (4) Halt if unknown locale silently falls through to English without `UnsupportedLocaleError`. (5) Halt if `SUPPORTED_LOCALES` ships without at least `en` and `es` entries per §2. |
| **Log tier** | `architectural` |
| **Risks & mitigations** | Kokoro voice ids may not exist for non-English locales — document in decision log; voice selection remains `kokoro_voice` / operator responsibility. Map SHA stale — verify `config.py` field list before edit. |

### T2 — Speaker uses config kokoro_lang_code

| Field | Content |
|-------|---------|
| **ID** | T2 |
| **Scope** | Replace hard-coded `KPipeline(lang_code="a")` with `config.kokoro_lang_code`; update `tests/test_speaker.py` (including rename of American-English-specific test name if needed). |
| **Files to touch** | `heckler/speaker.py`, `tests/test_speaker.py` |
| **Contract bindings** | §2 Types (Speaker), §2 Tests |
| **Inputs** | T1 (`kokoro_lang_code` on `HecklerConfig`, resolver landed) |
| **Outputs** | Speaker wired to config; updated speaker tests |
| **Kill criteria** | (1) Halt if context-map Flag 1 unresolved: literal `lang_code="a"` remains in `speaker.py` production path. (2) Halt if `test_init_uses_american_english_*` still asserts `lang_code="a"` when config supplies `kokoro_lang_code="e"` without amendment. (3) Halt if `HecklerConfig` or `locale.py` modified for new locales without T1 owning table (contract drift). |
| **Log tier** | `standard` |
| **Risks & mitigations** | Kokoro import in tests unchanged (existing shim). |

### T3 — Persona `[voice].locale` mapping

| Field | Content |
|-------|---------|
| **ID** | T3 |
| **Scope** | Extend `_TOML_TO_CONFIG` and ensure `apply_persona_overrides` re-resolves whisper/kokoro fields from merged `locale`; add persona tests with Spanish locale example. |
| **Files to touch** | `heckler/persona.py`, `tests/test_persona.py` |
| **Contract bindings** | §2 Types (persona), §2 Error envelope |
| **Inputs** | T1 (`apply_resolved_locale`, `resolve_locale`) |
| **Outputs** | Persona locale mapping + tests |
| **Kill criteria** | (1) Halt if context-map Flag 1 unresolved at execution start. (2) Halt if persona `locale` override updates `Reactor` path only — `apply_persona_overrides` must set `whisper_language` and `kokoro_lang_code` on returned config when `locale` present. (3) Halt if unmapped `[voice].locale` passthrough uses TOML-local name without hitting `HecklerConfig.locale` field. (4) Halt if `swap_persona` or controller rebuilt in this subtask. |
| **Log tier** | `standard` |
| **Risks & mitigations** | Persona bundle `prompts/heckler/` unchanged unless tests need fixture — optional doc-only in T5. |

### T4 — Controller load_models persona locale bake + hot-swap docs

| Field | Content |
|-------|---------|
| **ID** | T4 |
| **Scope** | `load_models(..., persona_name=...)` merges persona before constructing `Transcriber`/`Speaker`; document `swap_persona` STT/TTS limitation; add controller tests (persona locale baked at load; swap does not change transcriber language). |
| **Files to touch** | `heckler/controller.py`, `tests/test_controller.py`, `.dev/decision-logs/locale-lang-propagation-T4.md` (new) |
| **Contract bindings** | §2 Types (controller), §2 Tests |
| **Inputs** | T2 (Speaker uses `kokoro_lang_code`), T3 (persona locale overrides) |
| **Outputs** | Controller load path, tests, decision log |
| **Kill criteria** | (1) Halt if context-map Flag 2 unresolved at execution start: executor rebuilds `Transcriber`/`Speaker` inside `swap_persona` without plan amendment. (2) Halt if `load_models` still always passes raw `self._config` while persona TOML defines divergent `locale` and `persona_name` was available at load time. (3) Halt if test suite claims persona swap changes `Transcriber._config.whisper_language`. (4) Halt if `gui` or `pipeline.py` CLI flags added without amendment. |
| **Log tier** | `architectural` |
| **Risks & mitigations** | GUI may call `load_models()` before persona pick — document that operators should reload models after persona change for STT/TTS alignment (runtime-armed only for GUI until a future plan). |

### T5 — Operator docs and tracked plan bundle

| Field | Content |
|-------|---------|
| **ID** | T5 |
| **Scope** | README locale table + multilingual positioning; `.env.example` `HECKLER_LOCALE`; `CHANGELOG.MD` entry; commit `.dev/plans/locale-lang-propagation/`; optional one-line `.cursor/skills/persona_builder/SKILL.md` `[voice].locale` hint. |
| **Files to touch** | `README.md`, `.env.example`, `CHANGELOG.MD`, `.cursor/skills/persona_builder/SKILL.md` (optional), `.dev/plans/locale-lang-propagation/*` |
| **Contract bindings** | §2 Naming (`HECKLER_LOCALE`), §2 CLI N/A |
| **Inputs** | T4 (landed behavior) |
| **Outputs** | Docs; git-tracked plan bundle |
| **Kill criteria** | (1) Halt if README still states English-only without qualifying default locale / supported list. (2) Halt if `.env.example` documents `WHISPER_LANGUAGE` or raw Kokoro `lang_code` as operator env. (3) Halt if plan bundle left untracked. (4) Halt if `heckler_seed.md` edited without plan amendment (out of scope). |
| **Log tier** | `standard` |
| **Risks & mitigations** | README scope creep into GUI — stay env/persona/reload docs only. |

---

## §5 Adversarial pass

### 5.1 Rejected decompositions

1. **Split STT and TTS subtasks without shared locale field (parallel `whisper_language` env + `KOKORO_LANG` env):** Rejected — violates operator resolution for unified knob (Flag 1); reintroduces vocabulary collision (Whisper ISO vs Kokoro letters).
2. **Rebuild Transcriber/Speaker on every `swap_persona`:** Rejected — contradicts gui-T1 heavy-model ownership and operator Flag 2 resolution; expensive and racy on live mic.
3. **Six-way split (locale / config / speaker / transcriber / persona / controller / docs):** Rejected — transcriber already forwards `whisper_language`; separate transcriber subtask is mechanical with no contract anchor; increases packet coupling without parallel benefit.

### 5.2 Load-bearing assumptions

| Tuple |
|-------|
| (`Unified locale maps correctly to Whisper ISO and Kokoro letter` \| §2 Types → `heckler/locale.py:SUPPORTED_LOCALES` + `resolve_locale` \| STT and TTS diverge silently → wrong language pair shipped \| T1,T2,T3) |
| (`Kokoro accepts resolved lang_code for es/e and en/a,b` \| §2 Types → `Speaker.__init__` / Kokoro `LANG_CODES` \| `SpeakerError` at init on valid locale \| T2) |
| (`apply_resolved_locale runs after every persona merge` \| §2 Types → `apply_persona_overrides` \| persona `locale` changes gates path config but not whisper/kokoro fields \| T3) |
| (`Heavy models snapshot config at load_models` \| §2 Types → `PipelineController.load_models` \| persona TOML locale ignored for STT/TTS when load without persona_name \| T4) |
| (`swap_persona does not rebuild transcriber` \| §2 Types → `controller.swap_persona` \| hot-swap appears to change language but Whisper still uses load-time language \| T4) |
| (`whisper_language not read from env directly` \| §2 Types → `load_config` only `HECKLER_LOCALE` \| operators set WHISPER_LANGUAGE and expect it to work \| T1) |
| (`LLM register stays prompt-only` \| §1 non-goals \| scope creep into Reactor \| T5) |

### 5.3 Highest re-plan risk

**T4** — GUI/CLI call order (`load_models` before persona selection) may force either reload API or amended Flag 2 semantics; a packet-only executor might patch `start()` instead of `load_models` and reintroduce Surface 1 (merged `cfg` vs base `Transcriber`).

### 5.4 Hidden couplings

| Tuple | Status |
|-------|--------|
| (`Transcriber constructed with self._config in load_models while workers get merged cfg` \| `controller.py:load_models` + `_start_persona_mode` \| persona env gates differ from STT language \| T4) | **confirmed** (context-map Surface 1) |
| (`Speaker hard-coded lang_code="a"` \| `speaker.py:35` \| Spanish kokoro_voice with English phonemizer \| T2) | **confirmed** (context-map Surface 2) |
| (`load_config skips whisper_language` \| `config.py:load_config` \| HECKLER_LOCALE lands without resolver hook \| T1) | **confirmed** (context-map Surface 3 / Flag 4) |
| (`test_speaker asserts lang_code="a"` \| `tests/test_speaker.py:test_init_uses_american_english_*` \| T2 passes without driving config.kokoro_lang_code \| T2) | **confirmed** |
| (`test_controller swap_persona mocks may hide transcriber config` \| `tests/test_controller.py` \| false confidence on hot-swap \| T4) | **suspected** — disproven by explicit transcriber `_config.whisper_language` assertion test in T4 |
| (`prompts/heckler lacks locale key` \| `prompts/heckler/persona.toml` \| shipped persona stays English until operator edits \| T5) | **confirmed** — informational |
| (`README English-only positioning` \| `README.md:L3` \| operators think locale knob is no-op \| T5) | **confirmed** |

---

## §6 Executor packets

| Packet | Path |
|--------|------|
| T1 | `.dev/plans/locale-lang-propagation/packets/T1.md` |
| T2 | `.dev/plans/locale-lang-propagation/packets/T2.md` |
| T3 | `.dev/plans/locale-lang-propagation/packets/T3.md` |
| T4 | `.dev/plans/locale-lang-propagation/packets/T4.md` |
| T5 | `.dev/plans/locale-lang-propagation/packets/T5.md` |
| T6 | `.dev/plans/locale-lang-propagation/packets/T6.md` |
| T7 | `.dev/plans/locale-lang-propagation/packets/T7.md` |
| T8 | `.dev/plans/locale-lang-propagation/packets/T8.md` |

---

## §7 Amendment subtasks

*Triggered by audit `.dev/audits/2026-05-22-locale-lang-propagation.md` revision 1 (**fail**). Closes **FIND-04**, **FIND-05**, **FIND-06**; **FIND-02/03** via **T8** plan commit.*

```mermaid
graph LR
    T6["T6: CLI pipeline load_models"]
    T7["T7: GUI ModelLoadThread"]
    T8["T8: plan §8 + audit cross-link"]

    T6 --> T8
    T7 --> T8
```

**Parallel groups:** `{T6, T7}`.

### T6 — CLI: pass `persona_name` into `load_models` + integration test

| Field | Content |
|-------|---------|
| **ID** | T6 |
| **Scope** | Wire `heckler/pipeline.py` `main()` so `load_models` receives the same `persona_name` used by `start()` when `mode == "persona"`. Add falsifying test mirroring audit scenario A4. |
| **Files to touch** | `heckler/pipeline.py`, `tests/test_pipeline.py` |
| **Contract bindings** | §2 Entry-point integration (T6), §2 Tests |
| **Inputs** | T4 (controller `load_models(persona_name=...)` landed @ `093ce56f`) |
| **Outputs** | CLI wiring; pipeline test; optional one-line README “headless path” clarification if still ambiguous |
| **Kill criteria** | (1) Halt if `load_models` still omits `persona_name` on persona-mode `main()` path. (2) Halt if new CLI flags added. (3) Halt if test only mocks `start()` but not `load_models` persona propagation. (4) Halt if transcribe mode passes non-None `persona_name` without plan amendment. |
| **Log tier** | `standard` |
| **Risks & mitigations** | `PersonaNotFoundError` at load vs start — acceptable; load may fail earlier (document in test). |

### T7 — GUI: pass `persona_name` + `mode` into `load_models` + test

| Field | Content |
|-------|---------|
| **ID** | T7 |
| **Scope** | Extend `ModelLoadThread` to call `load_models(on_progress=..., mode=..., persona_name=...)` using `HecklerConfig` defaults (persona mode: `config.persona_name`; transcribe: `persona_name=None`). Update `tests/test_gui.py` assertion. Short decision log. |
| **Files to touch** | `heckler/gui/app.py`, `tests/test_gui.py`, `.dev/decision-logs/locale-lang-propagation-T7.md` (new) |
| **Contract bindings** | §2 Entry-point integration (T7), §2 Tests |
| **Inputs** | T4, T5 (GUI loads before `start()` documented) |
| **Outputs** | GUI wiring; gui test; decision log |
| **Kill criteria** | (1) Halt if FIND-05 unresolved: `ModelLoadThread` still calls `load_models()` with no `persona_name` in persona mode. (2) Halt if executor adds locale picker UI (plan non-goal). (3) Halt if `swap_persona` rebuilds Transcriber/Speaker. (4) Halt if persona-combo change while running triggers reload without plan amendment. |
| **Log tier** | `standard` |
| **Risks & mitigations** | Combo disabled until running — startup `config.persona_name` matches pre-start combo index; document in T7 log. |

### T8 — Plan §8 remediation + audit cross-link (narrative)

| Field | Content |
|-------|---------|
| **ID** | T8 |
| **Scope** | Commit plan v1.2.0 (this file + packets T6–T8); correct §8.1 hygiene, §8.4 Surface 1 disposition, §8.6 audit cross-link; supersede v1.1.0 “safe for audit” execution review. No runtime code. |
| **Files to touch** | `.dev/plans/locale-lang-propagation/plan.md`, `.dev/plans/locale-lang-propagation/packets/T6.md`, `T7.md`, `T8.md`, `.dev/audits/2026-05-22-locale-lang-propagation.md` (optional status footnote only if project convention allows) |
| **Contract bindings** | §7 amendment DoD (narrative back-annotate) |
| **Inputs** | T6, T7 (landed); audit FIND-02/03/06 |
| **Outputs** | Tracked plan v1.2.0 with valid §8 at amendment SHA |
| **Kill criteria** | (1) Halt if §8.4 still marks Surface 1 **closed** before T6/T7 land. (2) Halt if §8.1 claims “transcripts only” while plan.md unstaged. (3) Halt if §8.6 absent after amendment. |
| **Log tier** | `standard` |
| **Risks & mitigations** | T8 should land in same commit as T6/T7 or immediately after so §8.2 `git show` resolves. |

---

## §8 Auditor handoff

### §8.1 Completion snapshot

| Field | Value |
|-------|-------|
| **Handoff tree SHA** | `03c779e745ce2e6a8019225609dfd0734d441662` (T8 — plan §8 + audit tracked; code chain `d0ce6d0` T5 → `344ca19d` T7 → `4739b325` T6) |
| **Verification command** | `pytest tests/test_locale.py tests/test_config.py tests/test_speaker.py tests/test_persona.py tests/test_controller.py tests/test_pipeline.py tests/test_gui.py -q` |
| **Checkout** | `git checkout 03c779e745ce2e6a8019225609dfd0734d441662` — `plan.md` §8.1–§8.6 and `.dev/audits/2026-05-22-locale-lang-propagation.md` resolve in-tree at closure SHA (remediates FIND-02/03) |
| **Result** | **146 passed** in 4.03s, exit code **0** |
| **Prior SHA** | `d0ce6d0ee22b83aa988c1bfbeca2b5d5fffc38f8` (v1.1.0 — audit **fail** @ `.dev/audits/2026-05-22-locale-lang-propagation.md`) |
| **Environment** | Windows, project venv (implicit in local run) |

### §8.2 Artifact chain

| Artifact | Path | `git show 03c779e745ce2e6a8019225609dfd0734d441662:<path>` |
|----------|------|--------------------------------------|
| Context map | `.dev/plans/locale-lang-propagation/context-map.md` | OK — scout SHA `56c3748` (stale vs handoff; scope and coupling surfaces still valid) |
| Plan | `.dev/plans/locale-lang-propagation/plan.md` | OK — v1.2.0 §8.1–§8.6 at closure SHA |
| Packet T1–T5 | `.dev/plans/locale-lang-propagation/packets/T1.md` … `T5.md` | OK |
| Packet T6–T8 | `.dev/plans/locale-lang-propagation/packets/T6.md` … `T8.md` | OK (amendment wave) |
| Audit | `.dev/audits/2026-05-22-locale-lang-propagation.md` | OK — rev 1 fail; §8.6 back-annotates remediation |
| Decision log T1 | `.dev/decision-logs/locale-lang-propagation-T1.md` | OK |
| Decision log T4 | `.dev/decision-logs/locale-lang-propagation-T4.md` | OK |
| Decision log T7 | `.dev/decision-logs/locale-lang-propagation-T7.md` | OK |
| Changelog | `CHANGELOG.MD` (locale-lang-propagation section) | OK — T1–T8 entries |

### §8.3 §2 evidence (landed)

| §2 row | Shipped artifact | Proof |
|--------|------------------|-------|
| **Types — `heckler/locale.py`** | `heckler/locale.py:3-33` (`UnsupportedLocaleError`, `LocaleProfile`, `SUPPORTED_LOCALES`, `normalize_locale`, `resolve_locale`) | `tests/test_locale.py` (`test_resolve_locale_supported_keys`, `test_resolve_locale_unknown_raises_not_english_fallback`, `test_supported_locales_includes_en_and_es`) |
| **Types — `HecklerConfig.locale` / `kokoro_lang_code`** | `heckler/config.py:21-23` | `test_heckler_config_locale_defaults_resolved`, `test_apply_resolved_locale_*` |
| **Types — `apply_resolved_locale`** | `heckler/config.py:51-57` | `test_apply_resolved_locale_sets_derived_fields`, `test_apply_resolved_locale_en_gb_uses_british_kokoro_code` |
| **Types — `load_config` + `HECKLER_LOCALE`** | `heckler/config.py:74-75`, `94` | `test_load_config_heckler_locale_env_override`, `test_load_config_heckler_locale_whitespace_falls_back_to_en`, `test_load_config_heckler_locale_unknown_raises` |
| **Types — `Speaker` / `KPipeline(lang_code=...)`** | `heckler/speaker.py:35` | `test_init_uses_config_kokoro_lang_code_*`, `test_init_passes_resolved_kokoro_lang_code_to_pipeline` (parametrize `en`/`en-gb`/`es`) |
| **Types — `transcriber` (unchanged)** | `heckler/transcriber.py` uses `self._config.whisper_language` | `tests/test_transcriber.py` (`language` kwarg assertion) |
| **Types — persona `[voice].locale`** | `heckler/persona.py:32`, `129` | `test_load_persona_flattens_voice_locale`, `test_apply_persona_overrides_resolves_spanish_locale`, `test_apply_persona_overrides_rejects_unknown_locale` |
| **Types — `load_models(persona_name=...)`** | `heckler/controller.py:107-141`, `294-299` | `test_load_models_persona_name_bakes_spanish_locale`, `test_load_models_without_persona_resolves_base_locale` |
| **Types — `swap_persona` no STT/TTS rebuild** | `heckler/controller.py:256-276` (docstring; Reactor-only) | `test_swap_persona_does_not_change_transcriber_whisper_language` |
| **Error envelope** | `UnsupportedLocaleError` at resolve/apply/load | `test_resolve_locale_unknown_raises_*`, `test_load_config_heckler_locale_unknown_raises`, persona unknown-locale test |
| **Naming** | `HECKLER_LOCALE`, `locale`, `kokoro_lang_code`, decision log paths | Grep + `README.md`, `.env.example`, `persona_builder` SKILL |
| **Logging** | N/A (no new fields) | — |
| **Tests** | Seven modules per §2 (amendment) | §8.1 run: **146 passed** |
| **CLI surface** | N/A | No new flags in `heckler/pipeline.py` |
| **Entry-point — CLI (T6)** | `heckler/pipeline.py:374-377` | `tests/test_pipeline.py` — `load_models` receives `persona_name` on persona path |
| **Entry-point — GUI (T7)** | `heckler/gui/app.py` — `ModelLoadThread` | `tests/test_gui.py` — `load_models` kwargs `mode` + `persona_name` |

**Landed (docs, T5):** `README.md` multilingual positioning + locale table; `.env.example` `HECKLER_LOCALE`; `CHANGELOG.MD` locale-lang-propagation section; `.cursor/skills/persona_builder/SKILL.md` `[voice].locale` row.

**Deferred (documented, non-blocking):** No test that a hypothetical `WHISPER_LANGUAGE` env is ignored (`locale-lang-propagation-T1.md`); no test that second `load_models(persona_name=...)` replaces an already-loaded transcriber (`locale-lang-propagation-T4.md`); no pytest sync of README locale list vs `SUPPORTED_LOCALES` (`CHANGELOG.MD` T5 note).

### §8.4 §5 disposition

| §5.2 / §5.4 item | Status | Evidence |
|------------------|--------|----------|
| Unified locale → Whisper + Kokoro (§5.2) | **closed** | `SUPPORTED_LOCALES` + `apply_resolved_locale`; speaker/transcriber tests |
| Kokoro accepts `a`/`b`/`e` (§5.2) | **closed** | `test_init_passes_resolved_kokoro_lang_code_to_pipeline` |
| `apply_resolved_locale` after persona merge (§5.2) | **closed** | `apply_persona_overrides` → `apply_resolved_locale` at `persona.py:129` |
| Heavy models snapshot at `load_models` (§5.2) | **closed** | `_heavy_model_config` + controller bake tests |
| `swap_persona` does not rebuild transcriber (§5.2) | **closed** | Implementation + `test_swap_persona_does_not_change_transcriber_whisper_language` |
| `whisper_language` not env-direct (§5.2) | **closed** | Only `HECKLER_LOCALE` in `load_config`; no `WHISPER_LANGUAGE` wiring |
| LLM register prompt-only (§5.2) | **closed** | No Reactor/config LLM-locale field; §1 non-goals honored |
| Transcriber base vs merged cfg (§5.4) | **closed** | T6 `pipeline.py` + T7 `gui/app.py` pass `persona_name` into `load_models`; falsifiers in `test_pipeline.py` / `test_gui.py` (FIND-04/05/06 remediated) |
| Speaker hard-coded `lang_code="a"` (§5.4) | **closed** | `speaker.py:35` uses `config.kokoro_lang_code` |
| `load_config` skipped language (§5.4) | **closed** | `HECKLER_LOCALE` + `apply_resolved_locale` at end of `load_config` |
| `test_speaker` American-English-only assert (§5.4) | **closed** | Parametrized `test_init_passes_resolved_kokoro_lang_code_to_pipeline` |
| `test_controller` swap mocks hide transcriber config (§5.4, suspected) | **closed** | Explicit `Transcriber._config.whisper_language` assertion in T4 test |
| `prompts/heckler` lacks locale key (§5.4) | **treat-as-prediction** | Shipped bundle still English-default; operators opt in via TOML — informational |
| README English-only (§5.4) | **closed** | `README.md` L3 multilingual + locale table (T5) |

### §8.5 Cold-read seeds

Recommended narrative-blind Phase 0 read order:

1. `heckler/locale.py` — `SUPPORTED_LOCALES` and `resolve_locale` (contract anchor)
2. `heckler/config.py` — `apply_resolved_locale`, `load_config` + `HECKLER_LOCALE`
3. `heckler/controller.py` — `load_models`, `_heavy_model_config`, `swap_persona` docstrings
4. `heckler/speaker.py` — `KPipeline(lang_code=config.kokoro_lang_code)`
5. `tests/test_controller.py` — `test_load_models_persona_name_bakes_spanish_locale`, `test_swap_persona_does_not_change_transcriber_whisper_language`

### §8.6 Audit remediation cross-link

| Audit | Finding IDs | Amendment | Packet(s) | §2 / §8 back-annotate |
|-------|-------------|-----------|-----------|------------------------|
| `.dev/audits/2026-05-22-locale-lang-propagation.md` rev 1 | **FIND-04** CLI Surface 1 | Wire `persona_name` in `pipeline.py` `load_models` | **T6** @ `4739b325` | **remediated** — §2 Entry-point integration; §8.4 Surface 1 **closed** |
| Same | **FIND-05** GUI Surface 1 | Wire `persona_name` + `mode` in `ModelLoadThread` | **T7** @ `344ca19d` | **remediated** — same |
| Same | **FIND-06** §8.4 overstated | Correct disposition + execution review | **T8** | **remediated** — §8.4 row; v1.1.0 execution review superseded |
| Same | **FIND-02/03** plan §8 not in SHA / hygiene | Commit plan v1.2.0 at closure SHA | **T8** | **remediated** — §8.1–§8.2 resolve via `git show 03c779e745ce2e6a8019225609dfd0734d441662:plan.md` |

**Accepted deferrals (no amendment):** FIND-07 (`WHISPER_LANGUAGE` ignore test), FIND-08 (second `load_models` replace test), FIND-09 (README↔`SUPPORTED_LOCALES` pytest), FIND-01 (context-map stale — informational).

---

## Execution review (orchestrator)

**v1.1.0 pre-audit verdict (superseded):** Core resolver, config, Speaker, persona merge, and controller API matched §2; **audit failed** on production entry points (FIND-04/05/06) and plan §8 hygiene (FIND-02/03).

**v1.2.0 amendment verdict:** Surface 1 closed at `pipeline.py` and `gui/app.py` without changing Flag 2 hot-swap semantics. Amendment verification **146 passed** (§8.1). Re-audit recommended at `03c779e745ce2e6a8019225609dfd0734d441662` against `.dev/audits/2026-05-22-locale-lang-propagation.md` rev 1 findings.

| Subtask | Assessment |
|---------|------------|
| **T1–T5** | Landed @ `d0ce6d0` |
| **T6** | Landed @ `4739b325` — CLI `load_models(persona_name=...)` |
| **T7** | Landed @ `344ca19d` — GUI `ModelLoadThread` wiring |
| **T8** | Landed @ `03c779e745ce2e6a8019225609dfd0734d441662` — plan §8 + audit cross-link committed |
