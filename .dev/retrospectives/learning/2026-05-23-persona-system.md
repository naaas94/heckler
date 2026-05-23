# Learning retrospective — persona-system (deep pass)

**Date:** 2026-05-23  
**Primary sources:** `.dev/archive/persona-system/plan.md` (v1.1), `context-map.md`, `persona-system.md`, packets `T1.md`–`T7.md`, `.dev/audits/2026-05-16-persona-system.md` (revision 3), `.dev/decision-logs/persona-system-T1.md`, `persona-system-T3.md`, `.dev/decision-logs/T7.md` (reactor), `CHANGELOG.MD` (persona-system slice), current `heckler/persona.py`, `heckler/reactor.py`, `heckler/controller.py`, `prompts/heckler/*`.  
**Shorter first pass:** `.dev/retrospectives/learning/2026-05-16-persona-system.md`  
**Process twin:** `.dev/retrospectives/methodology/2026-05-23-persona-system.md`

---

## 1. Task context

**What shipped (2026-05-16):** Heckler stopped being “one hardcoded `prompts/system.md` + `Reactor` reads disk.” Personality became a **directory bundle** under `prompts/<id>/` (`persona.toml`, `system.md`, optional `examples.json`), loaded by **`heckler/persona.py`**, merged into **`HecklerConfig`** via **`apply_persona_overrides`**, and injected into **`Reactor(config, system_prompt, examples)`** with no filesystem I/O inside the reactor. Selection surfaced as **`HECKLER_PERSONA`**, **`HecklerConfig.persona_name`**, and **`--persona`**. Bad LLM `type` strings now yield **`CommentType.UNKNOWN`** (still score-gated) instead of **`None`**.

**Plan shape:** Seven subtasks — four parallel leaves (persona module, prompt migration, reactor refactor, config field), integrator (**pipeline wiring**), cross-cutting docs/tests, then **audit remediation** (context map regen, decision-log supersession, packet alignment). v1.0 implementation was sound; v1.1 closed documentation findings **FIND-01–03**; re-audit opened **FIND-ARCH-1** (`packets/T7.md` claimed in §8 but not in `HEAD` until later archive commit **`bb7746aa`** moved the bundle to `.dev/archive/persona-system/`).

**Why this deserves a *learning* retrospective (not only methodology):**

1. **Architectural tier** — new module + reactor seam + semantic change in `_parse_response`.
2. **It became the product’s extension point** — within a week, **gui-launcher** (hot-swap), **locale-lang-propagation** (`[voice].locale` on the same TOML mapping table), and **persona-speech-reload** (heavy-model signature when locale/voice changes) all hung off this bundle model. Understanding persona-system is prerequisite for every later “persona” task.
3. **The failure modes were cognitive** — green pytest, correct runtime, wrong *time-indexed* narrative and wrong *git* closure. That is a different class of lesson than “we forgot a test.”

---

## 2. What I now understand that I didn’t before

### 2.1 Three layers of “personality,” not one

Before this work, “persona” was implicit: files on disk + whatever `HecklerConfig` happened to be. After it, there are **three separable layers**:

| Layer | What it holds | Who owns it |
|-------|----------------|-------------|
| **Bundle** | Voice of the commentator (prompts, few-shots, per-persona TOML overrides) | `prompts/<id>/` + `load_persona` |
| **Runtime config** | Frozen `HecklerConfig` after `.env` + persona merge | `apply_persona_overrides` → pipeline/controller |
| **LLM shell** | How to call LiteLLM and parse JSON | `Reactor` (no bundle awareness) |

The plan’s best structural move was **not** passing a `Persona` object into `Reactor`, but passing **resolved strings and a merged config**. That keeps the reactor a pure “commentary engine” and lets **GUI hot-swap** replace only `Reactor` + config gates while leaving Whisper/Kokoro policy to later plans. I had conflated “swappable personality” with “one object that knows everything”; the shipped design splits **prompt content** from **speech stack** on purpose — and the later speech-reload plan exists because that split was load-bearing.

### 2.2 TOML ergonomics vs dataclass truth — the mapping table pattern

Operators think in **`pacing_interval`**; the code thinks in **`min_output_interval_s`**. If both names appear in the same namespace without a single mapping owner, overrides **silently do nothing** (WARNING only for keys that never made it into `config_overrides` with a valid field name).

The §2 table in the plan was not bureaucracy — it was the **anti-footgun layer** between author-facing TOML and `dataclasses.replace`. Implementation centralizes that in `_TOML_TO_CONFIG` in `persona.py`. The design doc’s sample `persona.toml` uses TOML-side names; only the plan §2 + code table make that safe.

**Residual sharp edge (plan §8 cold-read, still true today):** `_flatten_persona_toml` **passthrough** — unmapped keys inside `[voice]`/`[llm]`/`[gates]`/`[output]` keep their TOML-local names. If someone adds a TOML key that accidentally equals a `HecklerConfig` field name without going through the table, it can apply **without** hitting the “unknown key” WARNING path. Locale work later added `("voice", "locale") → "locale"` explicitly; that is the right habit for any new cross-cutting field.

### 2.3 `UNKNOWN` vs `None` is a product semantics choice, not a parser tweak

Previously, an unrecognized `type` string made `_parse_response` return **`None`**, which `react` treated like **`LLM_ERROR`** — the pipeline behaved as if the model failed. After the change, the same JSON can produce a **`ReactorResult`** with **`CommentType.UNKNOWN`** and still be killed by **score gate** if score is low.

So the behavior change is: **high-scoring responses with weird types can be spoken** instead of discarded. That matches the design doc’s “pragmatic enum, not per-persona schema yet.” I had underestimated how much **downstream observability** (logs, SQLite event types, operator mental model) depends on whether “bad type” looks like **model failure** vs **model succeeded with a label we don’t recognize**.

### 2.4 Parallel executors work when the contract is the lock, not the branch

`{persona module, prompt migration, reactor refactor, config field}` ran in parallel with **T5** as the only integrator. The plan explicitly allowed **reactor refactor** to implement against §2 **before** `heckler/persona.py` existed in-tree. That only works when:

- File ownership is disjoint.
- §2 freezes names, signatures, log strings, and test identifiers.
- Mid-DAG red tests are **documented** (T2 moved files while reactor still read root `prompts/` until T3/T6).

I used to think parallel agents needed strict land order; here, **land order mattered only at T5**, not among leaves. The synchronization primitive was the **contract document**, not git topology.

### 2.5 Prompt assets are “repo data,” not Python package data

T6 deliberately left `pyproject.toml` package find as `heckler*` only. Bundles live next to the repo root and resolve via `Path(__file__).parent.parent / "prompts"`. That is a **distribution choice**: editable checkout and dev layout work; `pip install .` without editable mode does **not** ship prompts. README documents that. For a side project operated from a clone, that is correct; for PyPI someday, packaging would need an explicit second decision — the plan did not pretend otherwise.

### 2.6 Context maps measure **baseline skew**, not moral failure

FIND-01 was: map generated at **`7b5382e`**, implementation changed paths under `prompts/heckler/` and added `persona.py`. The map was not “wrong” — it was **stale relative to a chosen SHA**. Post-land, the remediation is **regenerate at post-land HEAD** (`026d68d`) and document `git diff --quiet <map_sha> HEAD -- <path>` per row. I had treated “stale map” as scout incompetence; it is **version control for narrative artifacts**, same as code.

### 2.7 Decision logs are time series; “deferred” without a fence becomes lies

`persona-system-T3.md` **Items deferred** still described **`Reactor(config)` until T5** after T5 landed. A cold reader (or auditor) reasonably inferred that was **current**. FIND-02 fix: superseded block + **Landed** section pointing at `pipeline.py` and three-arg tests. Lesson: any bullet that describes **future** state must be **visually dead** once future arrives — banner, strike, or move to a “Historical” fence like `T7.md` (reactor) now does.

### 2.8 Downstream plans prove the seam was right — and incomplete on day one

Persona-system **non-goals** explicitly excluded GUI hot-swap and `[voice] enabled = false`. Within days:

- **gui-launcher** — `PipelineController.swap_persona` reloads bundle + swaps `Reactor` via `ReactorHolder`; same `load_persona` / `apply_persona_overrides` path.
- **locale-lang-propagation** — extended `_TOML_TO_CONFIG` with `locale`; `apply_persona_overrides` calls `apply_resolved_locale` after merge so persona `[voice].locale` affects `whisper_language` / `kokoro_lang_code`.
- **persona-speech-reload** — when locale/voice changes **speech stack signature**, heavy models reload; `swap_persona` alone is insufficient.

So persona-system was not “done” for the product — it was **done for v1 commentary swapping**. The bundle format was stable enough that later work **extended the mapping table** without reopening the reactor constructor. That is evidence the decomposition was right; it is also evidence **§2 should be treated as a living contract** when new fields (locale) appear.

---

## 3. Decisions I made and would make again

- **§2 as normative, design doc as informational** — `.dev/archive/persona-system/persona-system.md` still said “not yet implemented” while code shipped; the plan explicitly subordinated design prose to §2. That prevented `pacing_interval` prose drift from breaking merges.
- **`PersonaNotFoundError` subclasses `ValueError`** — pipeline can catch one type; operators get one startup failure class for missing dir / manifest / `system.md`.
- **Required `system.md`, optional `examples.json`** — empty examples list is valid; journal-style personas without few-shots are representable.
- **`[output].comment_types` informational-only** — avoids fake config keys and WARNING spam; defers per-persona schema validation to a later era.
- **Integrator subtask (pipeline wiring) after parallel leaves** — single place for `prompts_root` resolution, error message, and `Reactor(...)` construction; reduces duplicate path logic.
- **UNKNOWN fallback with unchanged score gate** — minimal behavioral surface; tests rename, not rewrite entire reactor suite.
- **T7 docs-only remediation** — FIND-01–03 did not require §2 reopen; correct scope discipline.
- **Hard cut** (`git mv` to `prompts/heckler/`, delete root copies) — `test_persona_prompt_bundle.py` guards against accidental resurrection of root layout.

**Generalizable principle:** Put **I/O and policy** in one module (`persona.py`), put **provider protocol** in another (`reactor.py`), put **wiring** in pipeline/controller — then later features attach to the middle layer without forking the LLM client.

---

## 4. Decisions I made that I would change

| Choice | Why it hurt | Better rule next time |
|--------|-------------|------------------------|
| §8 “Complete” while `packets/T7.md` untracked | FIND-ARCH-1; audit **`fail`** despite 202 green tests | Every §6/§8 path: `git show HEAD:<path>` or explicit “untracked — not claimed” |
| Permissive TOML passthrough in `_flatten_persona_toml` | Silent apply if TOML key collides with `HecklerConfig` field name | Prefer allowlist-only flatten; passthrough only for documented extension mechanism |
| Left plan §5.4 #1 evidence as `Reactor(config)` | Trains distrust in adversarial section even when disposition says “resolved” | When coupling resolves, update or strike the evidence line in the same amendment |
| Did not bump design doc status at v1.1 close | New readers anchor on “not implemented” timeline | One-line status + pointer to archive plan §2 |
| Persona T7 commit vs transcription-engine T6 | TE T6 **`git add`**’d plan bundle; persona T7 fixed map/logs but omitted packet from commit | Copy TE T6’s “artifact archaeology” checklist for any plan with §8.2 |

**Root error:** Confusing **narrative closure** (markdown says done) with **repository closure** (objects reachable from `HEAD`) and **product closure** (downstream features still coming).

---

## 5. Patterns in my own thinking

- **Asymmetry:** I grew confident in **parallel execution** because the code architecture rewarded it, but did not grow matching discipline for **artifact graphs**. Detail in the plan did not substitute for `git ls-files` on the last packet.
- **Auditor framing:** First reflex on FIND-01/02 was “pedantic docs.” More accurate frame: **time-indexed truth for multi-phase readers** — including future-me without chat context.
- **Sunk cost in plan quality:** A strong §5 adversarial pass did not prevent a one-file git slip; **checklists beat eloquence** at the boundary.
- **Extension blindness:** Non-goals listed GUI; I mentally filed persona-system as “finished” when it was only **finished for CLI commentary**. The GUI plan was already implicit in the design doc step 7 — should have tagged persona-system as **platform layer** in my head, not **feature complete**.
- **Review vs generation:** I learned the *shape* of the persona loader mainly by reading executor output and audits, not by holding the whole `_flatten_persona_toml` logic in working memory during planning. This retrospective is the pass where that logic becomes **mine** — especially passthrough and locale’s later hook.

---

## 6. Open questions

1. **Passthrough vs allowlist** — Is convention (“only use documented TOML keys”) enough, or should unknown keys inside known sections always WARN at flatten time?
2. **`[output]` beyond `comment_types`** — Should any other keys under `[output]` be ignored explicitly, or is passthrough intentional flexibility?
3. **`Persona` vs raw strings at `Reactor`** — Would passing `Persona` (or a small protocol) reduce duplicate field threading in controller/GUI, or re-couple the reactor to bundle shape?
4. **Per-persona `comment_types`** — When a persona needs a different JSON schema, is it a new reactor, a validator layer, or open enum + UNKNOWN forever?
5. **Packaging** — If Heckler is ever installed non-editably, is `package_data` for `prompts/` required, or is “personas live in user directory” the real model?
6. **Audit vs archive paths** — Audit rev 3 still cites `.dev/plans/persona-system/`; bundle lives under `.dev/archive/`. Does a revision 4 matter, or is archive + tracked `T7.md` enough for personal archaeology?

---

## 7. Single paragraph synthesis

Persona-system taught that **swappable personality is a boundary problem, not a file move**: bundle loader + config merge + injected prompts, with the reactor stripped of disk knowledge so GUI, locale, and speech-reload can attach later without forking LiteLLM. Contract-first parallel execution can ship **correct, tested runtime** while still failing the real gate — **traceability of planning artifacts to `HEAD` and to time** (map baselines, superseded deferred prose, packets that exist only in the editor). The compounding insight for future work: **treat §2 and the mapping table as the living API of `prompts/`**, run `git show HEAD:` on every §8 artifact before calling a plan complete, and mark platform layers as **extensible** even when v1 non-goals say “no GUI yet.”

---

## Appendix — artifact and commit anchors (for six-month-you)

| Item | Location / SHA |
|------|----------------|
| Archived plan v1.1 | `.dev/archive/persona-system/plan.md` |
| T7 packet (in `HEAD` at archive path) | `.dev/archive/persona-system/packets/T7.md` |
| Audit (verdict `fail` on FIND-ARCH-1) | `.dev/audits/2026-05-16-persona-system.md` rev 3 |
| Implementation closure (code) | `809ba456` family |
| T7 doc commit | `01f388e6` |
| Map regen baseline | `026d68d` |
| Archive move | `bb7746aa` |
| Default bundle | `prompts/heckler/persona.toml` |

**Downstream plans to read after this retrospective:** `gui-launcher`, `locale-lang-propagation`, `persona-speech-reload` (all assume persona-system seams).
