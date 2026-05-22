---
name: heckler-persona-creator
description: >-
  Create a new Heckler persona bundle (`prompts/<id>/`) that loads correctly
  with `load_persona`, behaves under pipeline gates, and is ready for hot-swap.
  Use when the user describes a new persona voice, commentary style, or
  behavioral profile and wants the three-file bundle produced and validated.
  Triggers on: "create a persona", "new persona for heckler", "add a persona",
  "persona bundle", or any description of a desired commentary style/voice
  followed by intent to run it in Heckler.
---

# Heckler Persona Creator

**Version:** 0.1 · **Owner:** Ale

## Purpose

Produce a valid `prompts/<persona_id>/` bundle — `persona.toml`, `system.md`,
`examples.json` — from a short user brief. The skill owns authoring and
validation. It does not modify application code; every constraint encoded here
is a contract enforced by existing code you cannot change.

**Pairing:** Hot-swap and config resolution live in `heckler/persona.py` and
`heckler/reactor.py`. If a requested behavior requires changing either file,
that is out of scope for this skill — flag it and stop.

---

## Input

A brief covering at minimum:

| Field | Required? | Example |
|-------|-----------|---------|
| Persona ID | Yes | `analyst`, `coach`, `interrogator` |
| Voice / tone | Yes | "dry academic, no jokes, deadpan delivery" |
| What it reacts to | Yes | "logical inconsistencies and hedging language" |
| What it avoids | Recommended | "personal attacks, profanity" |
| Spoken voice idea | Recommended | "slower, formal cadence" |
| Verbosity intent | Recommended | "one sentence max" |

If ID is missing, derive a slug from the tone. Confirm before writing files.

---

## Contract layer (hard constraints — do not negotiate)

### File tree

```
prompts/<persona_id>/
├── persona.toml   ← required
├── system.md      ← required
└── examples.json  ← required (see policy below)
```

`examples.json` is **required** by policy. The `Reactor._examples_block` is
always injected into the user message as "Examples of the register and quality
bar." An empty array produces a degraded prompt; this skill does not emit one.
Minimum: **5 examples**.

### persona.toml shape

```toml
[persona]
name = "<display name>"         # non-empty string — required
description = "<one sentence>"  # string — required

[voice]                         # optional section; omit keys you do not override
locale = "<en|en-us|en-gb|es>"  # optional; drives STT/TTS when heavy models load/reload (signature change)
kokoro_voice = "<id>"
kokoro_speed = <float>

[llm]                           # optional section
model = "<litellm model id>"
temperature = <float>
max_tokens = <int>

[gates]                         # optional section
score_threshold = <float 0–1>
pacing_interval = <float seconds>
density_threshold = <float 0–1>
min_word_count = <int>
```

**`_TOML_TO_CONFIG` mapping** (authoritative — `persona.py` line ~20):

| TOML `[section].key` | `HecklerConfig` field |
|----------------------|----------------------|
| `[voice].locale` | `locale` (resolved to `whisper_language` / `kokoro_lang_code` after merge) |
| `[voice].kokoro_voice` | `kokoro_voice` |
| `[voice].kokoro_speed` | `kokoro_speed` |
| `[llm].model` | `llm_model` |
| `[llm].temperature` | `llm_temperature` |
| `[llm].max_tokens` | `llm_max_tokens` |
| `[gates].score_threshold` | `score_threshold` |
| `[gates].pacing_interval` | `min_output_interval_s` |
| `[gates].density_threshold` | `density_threshold` |
| `[gates].min_word_count` | `min_word_count` |

Keys outside this table are silently ignored by `apply_persona_overrides` with
a warning log. Do not invent keys. `[output].comment_types` is explicitly
**not** consumed as a config override; omit it.

### system.md contract

The system prompt is injected as the **system** role message. The user message
template is assembled by `Reactor.react` and is **not controllable by the
persona**. It always has this shape (verbatim from `reactor.py`):

```
Examples of the register and quality bar:

<examples_block>

---

Recent context (last N utterances):
<context_block>

Current utterance to react to:
"<transcript>"

Respond with JSON only.
```

Therefore `system.md` **must**:

1. Define the role and behavioral constraints.
2. Declare the required JSON output shape with **all three keys**:
   `{"comment": string, "score": float, "type": string}`
3. State the `type` enum — valid values are exactly:
   `sarcasm | deflation | observation | absurdist | passive_aggressive | callback`
   (verify against `CommentType` enum in source if the codebase has been
   extended since this skill was written).
4. State the `score` semantics: float in `[0.0, 1.0]`; what the threshold means
   for this persona's gate (author's call, but must be documented in system.md).
5. State the word/length cap for `comment` (must be consistent with
   `max_tokens` and the persona's intended brevity).

`system.md` must **not** assume it can restructure the user message, add
context not in the assembled block, or change what field names the JSON uses.

### examples.json shape

```json
[
  {
    "transcript": "<utterance the persona reacts to>",
    "comment": "<the reaction>",
    "score": <float>,
    "type": "<CommentType value>"
  }
]
```

Every object **must** have exactly these four keys. Extra keys are tolerated by
`json.loads` but serve no purpose. Missing keys cause downstream parse errors.
`type` must be a valid `CommentType` string (see above). `score` must be a
float, not a string.

---

## Creative process

### Step 1 — Anchor the behavioral contract

One sentence: what is this persona *for* in the product? Not tone — purpose.
Example: "Deflates hedging and weasel-wording in technical discussions."
This sentence drives everything else. Write it before drafting any file.

### Step 2 — Design system.md

Structure:
1. **Role declaration** — Who is this? One or two sentences, no performance.
2. **Reactive target** — What specifically triggers a reaction? Be narrow.
3. **Avoidance list** — What the persona never does. Use explicit "Avoid:" block
   as in the reference persona.
4. **Scoring discipline** — Calibrate to the persona's style. A deadpan
   commentator reserves 0.85+ for lines with no escape hatch; an absurdist
   persona calibrates differently. State the calibration explicitly.
5. **JSON schema declaration** — Verbatim block, same keys as production.
6. **Type list** — Full `CommentType` enum, same format as reference persona.

Do not add sections that are not needed. Elegance here is achieved by removal.

### Step 3 — Design examples.json

Examples do two things simultaneously: teach **register** (voice, density,
wit-style) and establish **score calibration** (what does 0.85 mean for this
persona?). Both must be present.

Rules for a strong example set:
- Cover at least 3 distinct `type` values across 5+ examples.
- Include at least one example with `score >= 0.85` that demonstrates the
  ceiling for this persona's style.
- Include at least one example in the 0.70–0.79 range to anchor the middle.
- Transcripts should resemble realistic utterances the persona will encounter.
- Comments must be self-contained — no setup, no follow-up expected.
- Length of comments must be consistent with `max_tokens` and system.md's
  stated word cap.

Anti-patterns (explicitly exclude):
- Examples where the comment explains itself.
- Examples where the comment works only with context not in `transcript`.
- Generic reactions that would fit any transcript ("Interesting.").
- Scores that do not reflect the stated calibration in system.md.

### Step 4 — Set persona.toml overrides

Use the tuning guide below to set gate and LLM knobs. Only include sections
with actual overrides — an empty `[gates]` section adds noise.

---

## Tuning guide

### `score_threshold` vs personality

Higher threshold → fewer but higher-quality reactions. A dry wit persona should
be conservative (0.70–0.75) — it fires rarely and lands. A rapid-fire persona
can lower to 0.55–0.65 at the cost of more marginal output. Match the persona's
stated verbosity intent.

### `pacing_interval` vs annoyance

`pacing_interval` (`min_output_interval_s`) is the minimum seconds between
spoken outputs. Short-form reactive personas: 8–12 s. More contemplative
personas: 15–25 s. If the persona is explicitly a "rapid fire" style, go below
8 only intentionally — below 5 s creates overlapping audio.

### `temperature` and `max_tokens` vs wit vs stability

`temperature = 0.9` is the reference default. Higher (0.95–1.0) increases
lexical surprise but also increases output-shape failures (malformed JSON,
wrong keys). Lower (0.7–0.8) is more stable for analytical or formal personas
but reduces wit variance. `max_tokens = 150` is sufficient for ≤15-word
comments; increase only if the persona has explicitly longer output by design.

### Per-locale Kokoro voice table

| Locale slug | Kokoro `lang_code` | Compatible voice prefixes | Example |
|-------------|-------------------|---------------------------|---------|
| `en` / `en-us` | `a` | `af_*`, `am_*` | `af_sarah` |
| `en-gb` | `b` | `bf_*`, `bm_*` | `bf_emma` |
| `es` | `e` | `ef_*`, `em_*` | `ef_dora` |

**Rule:** Always match voice prefix to `lang_code`. Mixing (e.g. `af_sarah` with `locale = "es"`) sets the Spanish phonemizer but uses an English voice — sounds wrong. Heckler will warn in the status bar but will not block the reload.

### Kokoro voice vs character

`kokoro_voice` must be a valid Kokoro voice id. Match voice timbre to the spoken character: dry/formal personas pair better with lower-affect voices; energetic personas benefit from faster `kokoro_speed` (1.1–1.2). Do not set `kokoro_speed` below 0.85 (unnatural pacing) or above 1.3 (loss of intelligibility). Spanish personas should use `ef_*` / `em_*` voices (see table above), not `af_sarah`.

### `density_threshold` and `min_word_count`

`density_threshold` is the minimum lexical density score for an utterance to
pass the input gate. Higher values mean the persona reacts only to dense,
information-rich speech. For analytical personas targeting hedging: 0.45–0.55.
For social commentary personas: 0.35–0.40. `min_word_count` filters very short
utterances; 4 is the reference floor. Raise to 6–8 for personas that need
enough context before reacting.

---

## Validation checklist (HALT if any fails)

Before declaring the bundle ready:

- [ ] `prompts/<persona_id>/` directory exists with all three required files.
- [ ] `persona.toml` contains `[persona]` with non-empty `name` and `description`.
- [ ] All TOML keys in non-`[persona]` sections appear in `_TOML_TO_CONFIG` or
  are intentionally absent. No phantom keys.
- [ ] `system.md` declares JSON output with keys `comment`, `score`, `type`.
- [ ] `system.md` lists all valid `CommentType` values.
- [ ] `system.md` does not attempt to reshape the user message template.
- [ ] `examples.json` is a JSON array; `json.loads` succeeds.
- [ ] Every example object has exactly `transcript`, `comment`, `score`, `type`.
- [ ] Every `type` value is a valid `CommentType` string.
- [ ] Every `score` is a float in `[0.0, 1.0]`.
- [ ] At least 5 examples present.
- [ ] Comment length in examples is consistent with `max_tokens` and system.md
  word cap.
- [ ] `load_persona(Path("prompts/<persona_id>"))` would succeed given the
  stated logic in `persona.py` (walk through `_flatten_persona_toml` mentally
  or trace the code path).

If any check fails: fix before presenting the bundle. Do not present a bundle
that fails its own contract.

---

## Reference

`prompts/heckler/` is the canonical shape reference. Diff against it when
verifying output structure. Do not copy its voice or examples — that persona
is already deployed. The reference value is its file shape and key coverage,
not its content.

`CommentType` enum: verify against source before using, as it may have been
extended since this skill was written. The authoritative location is the enum
definition in the `heckler` package (search for `class CommentType`).

Hot-swap note: a new `Reactor` is constructed on the next utterance after
persona change. There is no session memory inside a persona — the `system.md`
cannot assume prior utterances have been seen under this persona. Do not write
examples that depend on contextual memory the persona cannot have.

---

## Out of scope

- Modifying `HecklerConfig` defaults, `Reactor`, or any application code.
- Creating personas with behaviors that require new `CommentType` values —
  that is a code change, not a persona authoring task.
- Evaluating whether a persona is "good" beyond structural validity — that
  requires live pipeline runs, which are outside this skill.
