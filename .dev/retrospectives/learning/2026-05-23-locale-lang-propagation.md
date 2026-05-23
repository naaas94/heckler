# Learning retrospective — locale-lang-propagation (deep)

**Date:** 2026-05-23  
**Task:** Unified **`HecklerConfig.locale`** knob (`HECKLER_LOCALE` + persona `[voice].locale`) → Whisper `whisper_language` + Kokoro `kokoro_lang_code`; load-time bake into `Transcriber`/`Speaker`; document hot-swap STT/TTS limits; **amendment** wire CLI/GUI `load_models` after audit **fail**.  
**Why this qualifies:** Two **architectural** subtasks (resolver module + controller bake), a **false-complete** v1 closure repaired only by adversarial audit, and a coupling surface that became **load-bearing** for the follow-on **persona-speech-reload** plan (`speech_stack_signature`, conditional reload).

**Artifacts reviewed (2026-05-23):**

| Layer | Paths |
|-------|--------|
| Plan / packets / map | `.dev/plans/locale-lang-propagation/plan.md` (v1.0→v1.3.0), `context-map.md`, `packets/T1.md`–`T8.md` |
| Process | `.dev/audits/2026-05-22-locale-lang-propagation.md` (rev 1 **fail** @ `d0ce6d0`, rev 2 **pass** @ `24ca9bd8`), `.dev/retrospectives/methodology/2026-05-23-locale-lang-propagation.md` |
| Decisions / changelog | `.dev/decision-logs/locale-lang-propagation-T1.md`, `T4.md`, `T7.md` (superseded banners), `CHANGELOG.MD` § locale-lang-propagation |
| Code / tests | `heckler/locale.py`, `config.py`, `persona.py`, `speaker.py`, `controller.py`, `pipeline.py`, `gui/app.py`; `tests/test_locale.py`, `test_config.py`, `test_speaker.py`, `test_persona.py`, `test_controller.py`, `test_pipeline.py`, `test_gui.py` |
| Git (locale wave) | `f1cb9a14` T1 → `02f8b58a` T2 → `680ca30e` T3 → `093ce56f` T4 → `d0ce6d0e` T5 → `4739b325` T6 → `344ca19d` T7 → `03c779e7`+ T8 → `24ca9bd8` closure |
| Downstream | `persona-speech-reload` (supersedes T4/T7 “swap never rebuilds” / frozen `config.persona_name`); audit addendum FIND-A6 closed |

**Methodology twin:** `.dev/retrospectives/methodology/2026-05-23-locale-lang-propagation.md` — process, HALTs, amendment cycles. **This file** — domain, stack, and judgment patterns worth compounding.

---

## 1. Task context

**What shipped (May 2026).** Operators get one slug (`en`, `en-us`, `en-gb`, `es`) that resolves to aligned STT/TTS codes via `heckler/locale.py`. Config construction fails fast on unknown locales (`UnsupportedLocaleError`). `Speaker` no longer hard-codes Kokoro `lang_code="a"`. `PipelineController.load_models(..., persona_name=...)` builds heavy models from persona-merged, locale-resolved config. `swap_persona` in v1 only swapped `Reactor` — STT/TTS language stayed load-time fixed until explicit reload. Docs and `.env.example` document `HECKLER_LOCALE` (not raw Whisper/Kokoro env vars).

**What almost shipped instead.** At T5 closure (`d0ce6d0`), the resolver, controller API, and **101** module-level tests were green — but `python -m heckler` and the GUI still called `load_models()` **without** `persona_name`, so a Spanish persona TOML could leave Whisper on English while workers saw merged Spanish config (context-map **Surface 1**). Plan §8.4 marked that surface **closed** anyway. Audit rev 1 **`fail`**; amendment **T6/T7** (two-line wiring + kwargs falsifiers) + **T8** (plan §8 archaeology) landed @ `24ca9bd8`; rev 2 **`pass`**, **146** pytest.

**Timeline anchor:** Scout **2026-05-17** (`56c3748`) → execution/audit **2026-05-22** → learning retro **2026-05-23**. Same week as **persona-speech-reload**, which superseded the v1 operator contract (“change persona locale only via restart / manual `load_models`”) with signature-based conditional reload and GUI apply flows.

---

## 2. What I now understand that I didn’t before

### 2.1 Domain: locale is a propagation graph, not a config field

Adding `locale` to `HecklerConfig` was the easy part. The product bug was **three configs in flight**:

1. **Base** `self._config` on the controller (env + defaults).
2. **Merged** `cfg` at `start()` / `_start_persona_mode` (`apply_persona_overrides`) — gates, Reactor, worker kwargs.
3. **Frozen** `Transcriber._config` / `Speaker._config` at **`load_models`** construction time.

Whisper reads `language=self._config.whisper_language` from the object passed to `Transcriber.__init__`, not from whatever the worker thread “thinks” the session locale is. So “persona locale works” is false until **every path that constructs heavy models** passes the same `persona_name` (and later `locale_override`) the user will run under.

That is why Surface 1 was the real deliverable, not `heckler/locale.py`. The scout named it in May; the v1.0 DAG treated it as **T4-only** (`controller.py` in `files-to-touch`) while listing `pipeline.py` as **adjacent** and **excluding** `heckler/gui/**` from scope — yet both were production callers of `load_models`.

**Mental model I want to keep:** For any new “global knob” that affects **constructed** subsystems (models, codecs, phonemizers), draw a small diagram: *who calls the constructor, with which config snapshot, and when relative to persona merge?* If the answer is not identical across CLI, GUI, and tests, the feature is not done.

### 2.2 Domain: one product knob, two vendor alphabets

Flag 1 was not pedantry. Whisper wants ISO 639-1 (`en`, `es`). Kokoro wants single-letter `lang_code` (`a`, `b`, `e`) per its `LANG_CODES` / aliases. Letting operators set either independently recreates silent failure: Spanish transcript + English phonemizer is worse than “unsupported locale” because it **runs**.

The landed pattern — operator slug → `LocaleProfile` → derived `whisper_language` + `kokoro_lang_code` → **`apply_resolved_locale` after every merge** (`load_config`, `apply_persona_overrides`, locale override replace) — is the right default for any future stack (e.g. a third vendor with a third encoding). The mapping table in code (`SUPPORTED_LOCALES`) is the contract anchor; README table is operator documentation, not the source of truth (FIND-09: no pytest sync — accepted, but I should not forget the drift risk).

**Voice ≠ language.** `kokoro_voice` stays independent. Spanish `locale` → `kokoro_lang_code="e"` does not imply a valid Spanish voice id; T1 decision log says so explicitly. Product copy and persona_builder tables need to say “pick a voice compatible with resolved lang_code,” not “set locale and forget voice.”

### 2.3 Stack: heavy vs light split extends to “speech stack identity”

From **gui-launcher** I already had: `Transcriber`/`Speaker` are **heavy** and pinned; `Reactor`/queues are **light** and rebuilt. Locale-lang-propagation added: **speech language is a property of the heavy stack**, not of `swap_persona`.

v1 chose **document + test the limitation** rather than rebuild on every persona change (Flag 2, gui-T1 ownership, mic safety). That was coherent engineering for v1 and matched “expensive, racy reload” — but it was **wrong for real GUI/CLI use** once operators could pick personas with different `[voice].locale`. I felt the tension only after shipping; **persona-speech-reload** fixed it with `(whisper_language, kokoro_lang_code)` signature comparison and `ensure_heavy_models` / ask-dialog reload.

**Lesson:** “We won’t rebuild on swap” is a **performance/safety** tradeoff, not a substitute for **detecting when rebuild is required**. If the product allows persona or locale change after load, the controller needs a **predicate** (`heavy_models_need_reload`) and a **single reload entry point**, not a paragraph in README.

### 2.4 Stack: fail-fast at config construction beats fail-late at first audio

`UnsupportedLocaleError` at `resolve_locale` / `load_config` means misconfiguration surfaces in CI, at GUI startup, or when loading a bad persona — not on first `transcribe()` after ten minutes of live mic. That matches how other `HECKLER_*` env vars are tested (strip, whitespace → default). I should default to the same pattern for the next enumerated operator knob (sample rate presets, device profiles, etc.): **validate when building config**, not when touching hardware.

### 2.5 Process lesson that is also a technical lesson: green unit tests can certify a broken product

At `d0ce6d0`:

- `test_load_models_persona_name_bakes_spanish_locale` — **pass** (calls controller with `persona_name` explicitly).
- Default `main()` — **fail** audit scenario A4 (never passed `persona_name`).

The test proved the **API**; it did not prove the **wiring**. Amendment T6/T7 added kwargs capture on `PipelineController.load_models` from `main()` / `ModelLoadThread` — minimal, fast, sufficient for audit closure, but still not “Spanish Whisper at GUI boot with real TOML” (deferred in T7 log).

**What I now believe:** For integration seams flagged **confirmed** in a context map, require at least one test that executes the **entry-point function** (`main`, `ModelLoadThread.run`) or an explicit §8.4 row marked **open** until that exists. Controller-only tests are necessary, not sufficient.

### 2.6 Adversarial audit cold-read was the real integration test

Rev 1 Phase 0 read `pipeline.py` and `gui/app.py` **before** trusting plan §8. That ordering found CR-01/02 while §8.4 said Surface 1 closed — **narrative-concealment** (FIND-06). The methodology retro is right: the auditor did not “nitpick”; it caught a **class of false completion** I had started to accept (“we have a `load_models(persona_name=)` API, ship it”).

For my own pre-merge checklist (without waiting for audit): after any controller API change, `rg` for call sites of that method across `heckler/` and assert each path’s kwargs match the story in the plan.

### 2.7 What downstream supersession does and does not invalidate

**Still true and worth keeping:**

- `heckler/locale.py` as the only place that maps slug → Whisper/Kokoro pair.
- `apply_resolved_locale` after persona merge.
- `target_speech_config` / signature tuple for reload decisions (extended in current `controller.py`).

**Superseded (do not re-read T4/T7 logs without banners):**

- “`swap_persona` never rebuilds Transcriber/Speaker” — now **conditional** rebuild.
- “`ModelLoadThread` freezes `config.persona_name` at thread init” — now **callables** read at `run()` time.

The locale task’s **resolver and bake semantics** were prerequisites, not thrown away. The **operator UX contract** was incomplete until the next plan — and that is normal if plans are sliced by risk, but I should have flagged “GUI persona change while running” as a **known product hole** in v1 §8.4 as **open**, not buried in T4 “operators must call load_models again.”

---

## 3. Decisions I made and would make again

| Decision | Principle that generalizes |
|----------|---------------------------|
| **Single operator field `locale`** with internal derived fields | Product speaks one vocabulary; code owns vendor-specific encodings in one module. |
| **`heckler/locale.py` separate from `config.py`** | Keeps `load_config` readable and avoids circular imports; mapping table is testable in isolation (`tests/test_locale.py`). |
| **`UnsupportedLocaleError` instead of silent English fallback** | Misconfiguration should be loud; silent fallback hides wrong-language STT in production. |
| **`apply_resolved_locale` after `apply_persona_overrides`** | Any merge path that sets `locale` must refresh derived fields — one function, no duplicate mapping logic. |
| **`load_models(persona_name=...)` bake, not `swap_persona` rebuild (v1)** | Correct **first** step when heavy models are expensive; pair with signature predicate before claiming “hot-swap safe.” |
| **Explicit falsifier: `swap_persona` does not change `Transcriber._config.whisper_language` (v1)** | Documents frozen heavy config; prevents false confidence from mocks that never inspect `_config`. |
| **Amendment T6/T7 as wire-only subtasks after audit** | Small, reviewable fix for FIND-04/05; avoids scope creep (no locale picker in the same pass). |
| **Defer LLM “locale” to prompts (Flag 3 non-goal)** | STT/TTS alignment is mechanical; register is prompt craft — mixing them creates two sources of truth for “how the persona sounds.” |

---

## 4. Decisions I made that I would change

| Decision | What went wrong | Better rule next time |
|----------|-----------------|----------------------|
| **v1.0 DAG without T6/T7 (entry-point integration)** | Core feature worked in tests but not in `heckler` / `heckler-gui` default paths | If context-map lists a **confirmed** coupling on file X, X gets a subtask or §8.4 stays **open** until wired. |
| **Marking §8.4 Surface 1 closed at T5** | Conflated “controller API exists” with “production paths propagate persona locale” | Disposition language: **API closed** vs **integration closed** — never use one word for both. |
| **T4 packet `files-to-touch` = controller only** | Encouraged “API done = task done” while kill criterion 2 referenced `persona_name` **available at load time** on CLI/GUI | Kill criteria that mention “available at load time” imply **caller** tests in the same wave or a written deferral with open §8 row. |
| **Context map §Scope boundary excluding `heckler/gui/**`** | Surface 1 still depended on GUI `ModelLoadThread`; exclusion was about **picker UI**, not **load_models wiring** | Scope exclusions should say “no new widgets,” not “no touch gui package.” |
| **v1 operator story: “restart or manual reload” for persona locale change** | Accurate for code, hostile for GUI users who change combo while idle or running | If the GUI exposes persona selection, plan the **reload predicate** in the same epic or mark UX **known-broken** in README upfront. |
| **Trusting 101 tests without `test_pipeline` / `test_gui` in default verification command** | Amendment suite was always seven modules; v1 executors could run five and feel done | Plan §2 “Tests” row should list **minimum modules including all entry-point test files** for tasks with `pipeline.py` / `gui` callers. |
| **T8 SHA-align churn (`03c779e7` → `24ca9bd8`)** | Archaeology noise; v1.3.0 still drifted unstaged (R2-01) | One commit for §8 + amendment code; avoid “fix §8.1 SHA” commits unless release process requires it. |

---

## 5. Patterns in my own thinking

**Familiar move: “put the logic in the controller and test it well.”** That worked for gui-launcher lifecycle and failed the **last mile** here. I default to trusting architectural subtasks because they feel “hard”; wiring `persona_name=` into two call sites felt “too small to plan.” The audit proved the small wiring was the product.

**Over-trusted completion narrative.** Populated plan §8 on disk before it was in the closure SHA, then read §8.4 “closed” as comfort. That is the same failure mode as transcription-engine v1.0 untracked plan tree — I keep learning it in different costumes.

**Under-weighted adjacent rows in the file map.** `pipeline.py` was **adjacent**, not **direct**, so it never got a packet in v1.0. Adjacent in scout language means “not the primary edit surface,” not “safe to ignore for correctness.”

**Right pushback on scope:** Rejecting rebuild-on-every-`swap_persona` and rejecting split `WHISPER_LANGUAGE` / `KOKORO_LANG` env vars were correct product/engineering calls. The mistake was stopping documentation at “limitation” instead of shipping **detection + reload** when the GUI made the limitation visible.

**Motivated reading of kill criteria.** T4 kill criterion 2 was satisfied in `controller.py` while violated in `pipeline.py` — I let “halt if load_models passes raw config when persona locale diverges” mean “the method body is correct when called correctly,” not “the program calls it correctly.”

---

## 6. Open questions

- **How far should locale slugs go before a plan amendment?** `SUPPORTED_LOCALES` is a closed set; operators with `pt-BR` or `es-MX` expectations need either alias keys or a clear “use `es`” story. Is normalization + alias table the long-term pattern, or ICU-style locale negotiation?

- **Real-hardware matrix:** Tests mock Kokoro/Whisper. When does a locale deserve “verified on GPU” vs “mapping exists in code”? Spanish `es` + `kokoro_lang_code=e` + arbitrary `kokoro_voice` — what is the minimum operator recipe that actually sounds Spanish?

- **README / `SUPPORTED_LOCALES` drift:** Accepted deferral, but no linter. Worth a one-line codegen test or pre-commit, or is manual audit enough at this project size?

- **LLM register vs STT language:** Non-goal for v1 was right. As personas go multilingual, when does mismatch (English Whisper + Spanish system prompt) become a **supported** mode vs a footgun? No config field today — is prompt-only still sufficient at 10 personas?

- **Relationship to future i18n:** `locale` here is **model language**, not UI strings. If Heckler ever gets translated GUI labels, do we reuse the same slug or split `ui_locale` vs `speech_locale`?

---

## 7. Single paragraph synthesis

Locale-lang-propagation taught me that **a unified config knob is only as real as the construction graph it feeds**: Whisper and Kokoro do not read “the session config,” they read whatever `HecklerConfig` snapshot was frozen at `load_models`, while workers and Reactor can see a different merged config at `start()` — so passing tests on `PipelineController.load_models(persona_name=...)` meant nothing until CLI and GUI actually passed that argument, which the first audit caught and a two-subtask amendment fixed. The resolver module (`SUPPORTED_LOCALES`, fail-fast errors, `apply_resolved_locale` after persona merge) is durable; the v1 “hot-swap does not change language” story was an incomplete product contract that **persona-speech-reload** had to finish with signature-based reload. The compounding habit I want is: for every confirmed coupling surface in pre-plan exploration, either wire the caller in the same plan wave or leave §8 explicitly **open** — never mark integration closed because the hard part in the controller is done.
