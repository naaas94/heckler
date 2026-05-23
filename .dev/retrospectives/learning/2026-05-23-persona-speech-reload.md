# Learning retrospective — persona-speech-reload (deep pass)

**Date:** 2026-05-23  
**Primary sources:** `.dev/plans/persona-speech-reload/plan.md` (v1.1.0), `context-map.md`, packets `T1.md`–`T8.md`, binding spec `PERSONA_SPEECH_RELOAD.md`, `.dev/decision-logs/persona-speech-reload-T2.md`, `persona-speech-reload-T4.md`, `.dev/audits/2026-05-22-persona-speech-reload.md`, `.dev/audits/2026-05-22-locale-lang-propagation.md` (FIND-A6 addendum), `CHANGELOG.MD` (persona-speech-reload slice), landed code in `heckler/locale.py`, `heckler/controller.py`, `heckler/gui/main_window.py`, `heckler/gui/app.py`, `heckler/pipeline.py`, and tests.  
**Process twin:** `.dev/retrospectives/methodology/2026-05-23-persona-speech-reload.md` — HALTs, DAG, artifact hygiene, audit conditions. **This file** — domain, architecture, and judgment worth keeping.

**Upstream retros to read first:** `2026-05-23-locale-lang-propagation.md` (propagation graph, false-complete v1), `2026-05-23-gui-launcher.md` (controller as real GUI, `ModelLoadThread`), `2026-05-23-persona-system.md` (bundle vs speech stack split).

---

## 1. Task context

**What shipped (2026-05-22):** The third pass on “persona + locale → Whisper + Kokoro.” Operators can pick `heckler_arg` (Spanish TOML locale) in the GUI, optionally override speech locale via a **Speech locale** combo (`None` = “From persona”), and get **conditional** heavy-model reload when `(whisper_language, kokoro_lang_code)` changes — not when switching between two English personas. The controller gained `speech_stack_signature`, `target_speech_config`, `heavy_models_need_reload`, `ensure_heavy_models`, `reload_speech_stack_for_persona`, and `SpeechReloadPolicy`. The GUI gained `_apply_persona_and_speech` (auto on Start, ask while running), `_ReloadThread` for off-thread reload, and `ModelLoadThread` callables read at `run()` time. CLI `pipeline.main()` uses `ensure_heavy_models` as the sole startup load (no redundant `load_models`). `swap_persona` is explicitly **same-signature Reactor-only**; cross-locale work goes through reload + apply path. Prior audit finding **FIND-A6** (locale-lang: hot-swap did not rebuild STT/TTS) is closed with named tests.

**Plan shape:** Eight subtasks — locale helpers + track spec (T1), controller reload API (T2, architectural), GUI locale combo (T3), persona lifecycle + startup thread fix (T4, architectural), unified apply + ask dialog (T5), CLI parity (T6), scenario matrix + docs (T7), decision-log polish + audit addendum (T8). **No amendment cycle**, **zero executor HALTs**, cold audit **`pass-with-conditions`** @ `a5e5b96a` (implementation chain through `31228054`).

**Why this earns a *learning* retrospective (not only methodology):**

1. **Closes a multi-plan product arc** — persona-system (bundle), gui-launcher (controller + hot-swap), locale-lang-propagation (resolver + load-time bake + wiring amendment), then this plan fixes **when** reload happens and **what the GUI reads** at startup.
2. **Introduces a reusable pattern** — speech-stack **identity** as a tuple predicate, separate from persona **name** or Reactor **prompts**.
3. **Splits controller primitives from view orchestration** — the adversarial decomposition (reject putting ask dialog inside `swap_persona`) is a general MVC lesson, not Heckler-specific trivia.
4. **First-pass implementation was structurally sound** — unlike locale-lang v1, entry-point wiring was in-scope from the start; the learning is *why that worked* and what sharp edges remain (mock vs real models, `swap_persona` trust boundary).

**Git anchor:** `ae491c43` (T1) → `87549218` (T2) → `4b149019` (T3) → `c1861894` (T4) → `964f020c` (T5) → `78c945bf` (T6) → `2d924cdc` (T7) → `31228054` (T8) → `a5e5b96a` (plan bundle + transcripts).

---

## 2. What I now understand that I didn’t before

### 2.1 “Third and final fix” is three different failure modes, not one bug

The binding spec lists F1–F5 as separate failures. Treating them as one “locale bug” would have produced the wrong fix:

| Failure | Layer | Fix class |
|---------|--------|-----------|
| **F1** — startup load ignores combo | GUI thread reads **frozen** `HecklerConfig` at `ModelLoadThread` init | Callable snapshots at **`run()`** |
| **F2** — persona combo disabled until running | Widget gating inverted product intent | Enable when **models ready** + persona mode |
| **F3** — hot-swap updates Reactor only | Heavy models are **construction-time** snapshots | Signature predicate + reload path |
| **F4** — TOML locale irrelevant after wrong load | Same as F3 + F1 | `target_speech_config` + reload |
| **F5** — wrong Kokoro voice under Spanish `lang_code` | Voice id ≠ locale slug | Non-blocking prefix warning; reload still uses resolved `e` |

Locale-lang-propagation solved “how does `es` become `whisper_language` + `kokoro_lang_code`?” This plan solved “when do we **reconstruct** objects that already absorbed those fields?” and “what does the GUI pass into `load_models`?” I had mentally merged F3 with F1; they share symptoms (Spanish LLM, English TTS) but need different seams.

### 2.2 Speech-stack identity is not persona identity

**Persona name** is an operator label for a bundle (`prompts/<id>/`). **Speech-stack signature** is `(whisper_language, kokoro_lang_code)` after merge + resolve — two personas can share it (`heckler` and `technician` both English), or one persona can change signature when the operator overrides the locale combo.

Rejecting “reload keyed on persona name” (decision log T2, spec D1) was correct: a per-persona table would drift from `SUPPORTED_LOCALES`, ignore GUI override, and force reload when swapping English commentators. The predicate belongs on **resolved config**, not on **identity strings**.

`speech_stack_signature(cfg)` in `heckler/locale.py` is intentionally dumb: it reads already-resolved fields. Callers must run `target_speech_config` (persona merge + optional `locale_override` + `apply_resolved_locale`) first. That keeps comparison logic one place and makes “loaded vs target” a pure tuple inequality — the same pattern I want for any future heavy subsystem (e.g. a second STT engine) that is expensive to reconstruct.

### 2.3 Two lifetimes, now with an explicit reload bridge

The spec’s mermaid diagram (env/TOML → merge → resolve → **load** → heavy snapshot vs **start/swap** → Reactor/workers) is the picture to redraw for every “why doesn’t changing X update Y?” question.

Before this work I knew heavy vs light from gui-launcher. What crystallized here is the **missing arrow**: when merge+resolve produces a new signature, you must go through `reload_speech_stack_for_persona` (stop → load_models → start if was running), not through `swap_persona`. `swap_persona` only replaces `Reactor` under a **caller guarantee** that Whisper/Kokoro configs are unchanged.

`loaded_speech_stack()` reads `self._transcriber._config` — the **baked** snapshot, not `self._config` and not the worker’s merged cfg. That is why Surface 6 in the context map (“worker cfg vs Transcriber bake”) was **ruled out** once `target_speech_config` became the single derive path for both load and predicate.

### 2.4 Controller primitives vs GUI dispatch — load-bearing separation

The plan’s rejected alternative A — put ask dialog, combo revert, and reload policy inside `swap_persona` — would have failed for three independent reasons:

1. **Layering** — `PipelineController` has no Qt, no combo indices, no `QMessageBox`.
2. **Threading** — ask must run on GUI thread; reload blocks tens of seconds and belongs on `_ReloadThread`, not inside a method called from worker code paths.
3. **Ordering** — spec §18.1 / approval #7: on cross-locale change, **reload before Reactor swap**. `_apply_persona_and_speech` checks `heavy_models_need_reload` first; only the same-signature branch calls `swap_persona`.

So the public API surface splits cleanly:

- **Controller:** `target_speech_config`, `heavy_models_need_reload`, `ensure_heavy_models`, `reload_speech_stack_for_persona`, same-sig `swap_persona`.
- **View:** `_apply_persona_and_speech`, policy enum, mutex `_reloading`, cancel revert of **both** combos (D13).

Any future headless client (web UI, automation) should implement its own dispatch using the same primitives — not extend `swap_persona` with policy flags.

### 2.5 Callable snapshots beat “pass the window” or “pass config at init”

Flag 1 in the context map was ownership of **when** `ModelLoadThread` reads persona/locale. Three options were considered (decision log T4):

- **Window reference** — circular import risk, QWidget lifetime vs QThread lifetime.
- **Snapshot at `__init__`** — still wrong if user changes combo between thread construction and `run()`.
- **Callables at `run()`** — landed; matches “read UI state at thread start.”

Residual race after `run()` completes is explicitly covered by **D7 Start correction**: `ensure_heavy_models` before `start()` in `_on_start_stop`. That is a **second line of defense**, not an excuse to read combo at init. I should default to callables (or explicit “read UI now” at operation boundary) for any background loader tied to Qt widgets.

`ModelLoadThread` still calls `locale_override_fn()` in transcribe mode (audit CR-03) — combo hidden, low risk; worth knowing if transcribe ever gains locale semantics.

### 2.6 Sentinel rule: display strings are not API values

`selected_locale_override()` returns Python `None` for “From persona”, never the string `"From persona"`. That looks pedantic until you trace `resolve_locale("From persona")` → `UnsupportedLocaleError`.

The pattern generalizes: **GUI labels ≠ domain values**. Every boundary (combo → controller) needs an explicit conversion table. Tests like `test_target_speech_config_empty_locale_override_ignored` guard the `""` edge; the harder bug is passing the label string because a new developer copies combo text into `load_models`.

### 2.7 Reload policy is a product state machine, not a boolean “reload?”

`SpeechReloadPolicy`: `auto` | `ask` | `never`. Locked behavior (spec §24):

- **Not running** → no ask; Start uses `auto` through apply path.
- **Running** → persona/locale change uses `ask`; cancel reverts combos **without** swapping Reactor (reload-before-swap ordering preserved).

`never` exists for programmatic guardrails; the interesting path is ask + mutex. `_reloading` disables combos and reload button (G8/G13) so rapid en/es/en spam does not queue overlapping stop/load/start (S11). Debounce is **mutex + disable**, not a timer — simpler and testable.

### 2.8 CLI parity: `ensure_heavy_models` as sole startup load

T6 chose plan alternative C: drop redundant `load_models` + `ensure_heavy_models` double-call on CLI boot. On first run `loaded_speech_stack()` is `None`, so `ensure_heavy_models` always loads; on subsequent internal use, signature match makes it a no-op.

That unifies mental model: **“make heavy stack match target”** is one entry point for CLI and for GUI Start (via apply). Voice-only change, same locale → no reload (G14, non-goal for v1) falls out of signature equality without a special case.

### 2.9 What “done” still does not mean — mock matrix vs operator smoke

T7 named tests S1–S14 at mock level. Spec §20 exit criteria 1–3 remain **manual** (real Whisper/Kokoro, Spanish TTS audible). Audit **`pass-with-conditions`** explicitly accepts that gap (PSR-02).

I now treat three verification layers:

1. **Predicate/unit** — signature, sentinel, apply-path cancel/revert.
2. **Controller integration** — `test_speech_stack_cross_locale_reload_s2`, swap matrix.
3. **Operator smoke** — GUI boot + running reload — still the gate for declaring Spanish **sounds** right, especially with F5 voice mismatch warnings.

Green pytest does not replace layer 3 for audio products. This plan was honest about that; I should not let mock matrix greenness imply acoustic validation.

### 2.10 Sharp edge I accept: `swap_persona` does not enforce signature

Audit PSR-04 / cold-read CR-02: direct `swap_persona` after cross-locale load leaves English `Transcriber` while Reactor speaks Spanish. **By contract** — GUI always goes through `_apply_persona_and_speech`; docstrings and README say so.

That is the same class as “call `reload_speech_stack_for_persona` from wrong thread” — trust boundary on a **fast** primitive. Alternative would be runtime check in `swap_persona` (compare signatures, raise). Rejected for v1 to keep hot-swap cheap and avoid controller→GUI coupling. **Learning:** document sharp edges at the **primitive** that foot-guns; optional §2 row “enforcement: caller | runtime” in future plans.

### 2.11 How this plan relates to locale-lang-propagation (supersession without waste)

Nothing in `heckler/locale.py`’s resolver was thrown away. What was **superseded** was the **operator story**:

- T4 locale-lang decision: “swap never rebuilds STT/TTS” → banner + conditional rebuild.
- T7 locale-lang decision: “ModelLoadThread uses `config.persona_name` at init” → banner + callables.

FIND-A6 in the locale-lang audit was the formal statement of the product hole. This plan’s T8 addendum closes it with cited tests — good cross-plan hygiene.

The locale-lang learning retro’s regret — “mark integration open, not closed” — was **internalized** here: T6 wires CLI in the same epic; T4 fixes GUI startup in the same epic; T7 deletes the falsifier test that encoded the old contract. I did not repeat the “API closed = product closed” mistake for the reload predicate, though CHANGELOG still missed a T6 bullet (process leak, not runtime).

---

## 3. Decisions I made and would make again

| Decision | Principle that generalizes |
|----------|---------------------------|
| **Signature-only reload predicate** | Compare **derived physical identity** of expensive subsystems, not operator-facing names. |
| **`target_speech_config` as single derive path** for load + predicate | One function for “what would we build?” eliminates load-vs-start config drift. |
| **GUI `_apply_persona_and_speech` owns policy + revert + threading** | View orchestrates; controller mutates pipeline state. |
| **`_ReloadThread` mirrors `ModelLoadThread`** | Second long operation on GUI app → second QThread + signals, not blocking `exec()`. |
| **Callable snapshots in `ModelLoadThread`** | Read mutable UI at `run()`, not at thread construction. |
| **`None` sentinel for “From persona”** | Never pass display strings into resolvers. |
| **Reload before Reactor on cross-locale** | Order expensive/global state before cheap hot-swap. |
| **Supersede locale-lang T4/T7 logs with top banners** | Time-series logs need visible death marks when behavior inverts. |
| **Delete `test_swap_persona_does_not_change_transcriber_whisper_language`** | CI must not encode retired contracts; replace with matrix, not accumulate. |
| **Voice/locale prefix warning non-blocking** | Detect likely misconfiguration without refusing reload (F5). |
| **T3 → T4 → T5 sequence on `main_window.py`** | Accept serial GUI edits to avoid merge conflicts on shared handlers. |
| **Full orchestrator plan + packets despite spec §24 D12 “this file only”** | Large GUI+controller epics benefit from §2 contract tables executors can HALT against. |

---

## 4. Decisions I made that I would change

| Choice | What went wrong | Better rule next time |
|--------|-----------------|----------------------|
| **CHANGELOG omits T6** | Land commit `78c945bf` exists; persona-speech-reload section jumps T5 → T7 | Same checklist as methodology retro: **one bullet per landed subtask** before T8/audit. |
| **Plan + packets absent @ `31228054`** | §8.1 closure SHA not archaeology-complete until `a5e5b96a` | Commit `.dev/plans/<name>/` in **T8 commit** or set §8.1 SHA to bundle commit. |
| **`a5e5b96a` bundles `GUI_DARK_THEME.md` + transcript stubs** | Audit PSR-01; pollutes feature archaeology | Split commits: implementation chain vs docs vs one-line transcripts. |
| **T5 log tier `standard` despite §5.3 “highest re-plan risk”** | Calibration drift — worked, but under-labeled blast radius | Tier = f(plan §5.3 risk flag), not f(landed cleanly). |
| **No test: locale combo change while running without persona change** | PSR-03; CHANGELOG defers | If widget exists, wire + test one signal path or mark §8.4 **open**. |
| **Full pytest 349 count not re-verified in audit** | Same class as sibling plans | Auditor/environment runs full `-m "not heavy"` or §8.1 says “subset only.” |
| **Spec §24 D12 “artifacts = this doc only” then full plan tree** | Flag 4 ambiguity — resolved by user request, but spec text lagged | Update spec revision table when orchestration scope changes. |

**Root error (lighter than locale-lang v1, same family):** **repository/narrative completeness** lagged **implementation completeness**. Runtime was right earlier; git index and CHANGELOG caught up late.

---

## 5. Patterns in my own thinking

**Learned from locale-lang failure, applied here.** I was primed to ask “do `pipeline.main` and `ModelLoadThread.run` pass the right kwargs?” before calling the epic done. That showed up as T6 in the DAG and F1/F2 in the same plan as the reload API — not a follow-up amendment. The improvement is real; it should become automatic for any plan touching `load_models`.

**Still weak on artifact chain at closure.** Plan §8.2 honestly flagged absent-from-HEAD plan/packets, but I still emitted §8.1 at `31228054` instead of waiting one commit. I keep treating “handoff markdown exists on disk” as sufficient for six-months-later me; **`git show HEAD:plan.md`** is the only durable handoff.

**Correctly trusted adversarial decomposition on T5.** I would have been tempted to put reload inside `swap_persona` because spec §5.7 pseudo-code looks that way. The plan’s rejected alternative A saved a re-plan. **Read pseudo-code as intent, not placement.**

**Under-valued “adjacent” until locale-lang taught otherwise.** Here, `pipeline.py` was **direct** in T6 — good. `README` and `persona_builder` were T7 — appropriate deferral of docs until behavior exists.

**Confused “final fix” with “all locale work finished.”** Non-goals are explicit: no new locale slugs, no LLM locale knob, no persisting GUI override, no in-place Transcriber swap. “Final” means **this propagation class** (persona + override → heavy models) is closed for v1, not that Heckler is i18n-complete.

**Comfort with trust-boundary APIs.** Accepting unsigned `swap_persona` matches how I think about `ReactorHolder.get()` — performance and simplicity at the primitive, discipline at the call site. Risk: a future contributor calls `swap_persona` from a script without reading docstrings. Mitigation might be `logging.warning` on signature mismatch without blocking — worth weighing if misuse appears.

**Serial GUI subtasks when parallel was safe for T6.** T6 could have run beside T3 after T2; I left wall-clock on the table. Low pain this time; habit worth noticing.

---

## 6. Open questions

- **Runtime guard on `swap_persona`?** If internal tools or tests start calling it directly, does a signature check + clear `RuntimeError` pay for itself, or pollute the hot path?

- **Locale combo-only change while running** — product-intent unclear: should changing speech locale without persona change always trigger the same ask/reload flow? Wired or not?

- **Voice-only reload** — v1 non-goal (same signature). When Kokoro adds voices that need rebuild without locale change, does signature need a third field, or a separate “voice reload” primitive?

- **Acoustic acceptance** — what is the minimum manual script (S1–S3) worth recording as a checklist video or scripted smoke for releases?

- **`loaded_speech_stack` reads private `_transcriber._config`** — stable enough, or should Transcriber expose a read-only `speech_signature` property for encapsulation?

- **Config precedence row 1 (GUI override) vs persona TOML** — operators may not understand why override beats persona. UX copy vs docs only?

- **Fourth locale** — next slug addition is a plan amendment to `SUPPORTED_LOCALES`, GUI labels, persona_builder table, and signature tests — is there a checklist template from this epic?

---

## 7. Single paragraph synthesis

Persona-speech-reload taught me that **locale propagation in a live pipeline is a lifecycle problem**, not a mapping table problem: once Whisper and Kokoro are constructed, the only safe abstractions are a **resolved target config**, a **signature tuple** comparing target to loaded, and a **reload primitive** that stops the world when the tuple changes — while **persona hot-swap** stays a cheap Reactor swap only when the tuple does not. The GUI’s job is to read combo state at the right instant (callables at `run()`, `ensure_heavy_models` at Start), convert display sentinels to `None`, and own ask/cancel/revert on a background reload thread — never to smuggle dialogs into `swap_persona`. I applied the hard lesson from locale-lang-propagation (wire entry points in the same epic) and got a clean first-pass implementation; the remaining gaps are **artifact hygiene**, **CHANGELOG completeness**, and **manual acoustic smoke**, not missing controller logic. Six months from now, remember: **F1 and F3 are different bugs**, **`(whisper_language, kokoro_lang_code)` is the reload key**, and **green mock tests do not mean Spanish TTS sounds Spanish**.
