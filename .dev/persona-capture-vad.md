# Persona-scoped capture / VAD overrides

## Status: Proposed — not implemented

## Summary

Persona mode cuts microphone segments using **global** `HecklerConfig` capture defaults (`max_speech_duration_s = 15`, `silence_duration_ms = 800`). Persona bundles today override voice, LLM, and gates only — not how long the user may speak before Whisper and the reactor run.

The **technician** persona needs longer monologues and a **~2 s silence** boundary before end-of-utterance. That behavior should live in **`persona.toml`** (per persona), with a small wiring change in `heckler/persona.py`. Transcribe mode already solves a similar problem via `transcribe_*` fields and `dataclasses.replace` in `controller.py`; persona mode should reuse the same underlying config fields, not duplicate logic.

---

## Symptom

In persona mode with `technician` (or any persona), continuous speech is **force-closed at 15 seconds** even without silence. Brief pauses (~0.8 s) can also end a segment mid-thought. After segment close → transcribe → `Utterance` → LLM.

This is **not** caused by `pacing_interval`, `score_threshold`, or reactor content. It happens **before** the LLM.

---

## Where segmentation happens

```
Mic → AudioCapture (Silero VAD) → audio_queue → Transcriber → reaction pipeline
```

`AudioCapture` (`heckler/audio_capture.py`) closes a segment when **either**:

| Rule | Config field | Persona-mode default | Effect |
|------|----------------|----------------------|--------|
| Silence after speech | `silence_duration_ms` → Silero `min_silence_duration_ms` | **800 ms** | ~0.8 s quiet closes chunk |
| Hard cap while still speaking | `max_speech_duration_s` | **15.0 s** | Force emit at 15 s with no silence |
| Too short to keep | `min_speech_duration_ms` | **500 ms** | Drop segment below minimum length |

Relevant force-close logic:

```python
# heckler/audio_capture.py (simplified)
if capturing and pending >= max_speech_samples:
    self._emit_audio_segment(audio, min_speech_samples)
    # reset VAD — segment ends regardless of silence
```

---

## What persona.toml controls today

`_TOML_TO_CONFIG` in `heckler/persona.py` maps only:

| TOML section | Keys → `HecklerConfig` |
|--------------|-------------------------|
| `[voice]` | `kokoro_voice`, `kokoro_speed` |
| `[llm]` | `model`, `temperature`, `max_tokens` |
| `[gates]` | `score_threshold`, `pacing_interval`, `density_threshold`, `min_word_count` |

**Not mapped:** `max_speech_duration_s`, `silence_duration_ms`, `min_speech_duration_ms`, `vad_threshold`.

Persona mode startup (`PipelineController._start_persona_mode`):

1. `load_persona(...)`
2. `cfg = apply_persona_overrides(self._config, persona)`
3. `AudioCapture(cfg, audio_queue, is_playing)`

So VAD always uses base defaults unless changed globally.

---

## What transcribe mode already does

Transcribe mode does **not** use persona TOML; it `replace`s capture fields from dedicated config:

```python
# heckler/controller.py — _start_transcribe_mode
effective_config = dataclasses.replace(
    self._config,
    max_speech_duration_s=self._config.transcribe_max_speech_duration_s,
    silence_duration_ms=self._config.transcribe_silence_duration_ms,
    min_speech_duration_ms=self._config.transcribe_min_speech_duration_ms,
)
```

Defaults in `heckler/config.py`:

| Field | Default |
|-------|---------|
| `transcribe_max_speech_duration_s` | 45.0 |
| `transcribe_silence_duration_ms` | 1500 |
| `transcribe_min_speech_duration_ms` | 250 |

Persona mode never applies this `replace`. The “longer utterance” knobs exist on `HecklerConfig` but are only wired for transcribe.

---

## Proposed design: `[capture]` in persona.toml

### Shape

```toml
[capture]
max_speech_duration_s = 45.0
silence_duration_ms = 2000
min_speech_duration_ms = 250   # optional; omit to keep base default
```

Section name `[capture]` (or `[vad]`) — pick one and document in `persona_builder` skill. `[capture]` aligns with “microphone segmentation” rather than “transcribe-only mode.”

### Mapping (extend `_TOML_TO_CONFIG`)

| TOML `[capture].key` | `HecklerConfig` field |
|----------------------|------------------------|
| `max_speech_duration_s` | `max_speech_duration_s` |
| `silence_duration_ms` | `silence_duration_ms` |
| `min_speech_duration_ms` | `min_speech_duration_ms` |

Optional later: `vad_threshold` → `vad_threshold` if personas need sensitivity tuning.

### Merge behavior

Same as existing overrides: `apply_persona_overrides(base, persona)` → `dataclasses.replace` only for keys present in the persona bundle. Omitted `[capture]` section → global persona defaults (15 s / 800 ms).

### Hot-swap

`swap_persona` already rebuilds effective config from overrides. Once `[capture]` is mapped, a persona swap on a **running** session should apply new VAD values on the **next** `AudioCapture` cycle only if capture is restarted or config is pushed into a live capture instance. **Today** capture reads `self._config` at init — confirm whether hot-swap restarts capture or only reactor; if capture is not restarted, document that capture overrides require restart (or thread-safe config refresh as follow-up).

---

## Example: `prompts/technician/persona.toml`

Add after existing sections (values are product intent from discussion):

```toml
[capture]
max_speech_duration_s = 45.0
silence_duration_ms = 2000
min_speech_duration_ms = 250
```

Rationale:

- **2000 ms silence** — end segment after ~2 s quiet, not 0.8 s; reduces mid-question splits on short breaths.
- **45 s max speech** — matches transcribe-mode headroom; still caps unbroken monologue (continuous speech with no 2 s gap).
- **250 ms min speech** — optional alignment with transcribe; allows short “yes/no” without changing technician’s gate `min_word_count` (that gate is post-transcript, different concern).

---

## Implementation checklist

| Step | Location | Notes |
|------|----------|--------|
| 1 | `heckler/persona.py` | Add `("capture", ...)` entries to `_TOML_TO_CONFIG`; include `capture` in `_flatten_persona_toml` allowed sections (today: `voice`, `llm`, `gates`, `output`). |
| 2 | `tests/test_persona.py` | Round-trip: TOML `[capture]` → `apply_persona_overrides` → expected `HecklerConfig` fields. |
| 3 | `prompts/technician/persona.toml` | Add `[capture]` block (after code ships). |
| 4 | `.cursor/skills/persona_builder/SKILL.md` | Document `[capture]` keys and tuning guidance (silence vs max duration). |
| 5 | Hot-swap behavior | Verify GUI `swap_persona` + running `AudioCapture`; restart capture or document limitation. |

**Out of scope for persona bundle alone:** changing `audio_capture.py` to remove the hard cap entirely (silence-only segmentation). That would be a separate product decision.

---

## Alternatives

| Approach | Pros | Cons |
|----------|------|------|
| **Per-persona `[capture]` in TOML** (recommended) | Technician-only tuning; matches persona-system model | Requires `persona.py` change |
| **Global `HecklerConfig` / env defaults** | Trivial | Affects all personas (heckler gets long segments too) |
| **Controller special-case** (`if persona == "technician": replace(...)`) | Small diff | Not data-driven; doesn’t scale |
| **Switch to transcribe mode** | Already has loose VAD | No LLM/TTS reaction loop |

`load_config()` does **not** read VAD from environment today. Env overrides could be added globally but do not replace per-persona TOML.

---

## Related knobs (easy to confuse)

| Knob | Layer | What it does |
|------|--------|----------------|
| `max_speech_duration_s` / `silence_duration_ms` | **Capture** | When your speech becomes one Whisper chunk |
| `min_word_count` / `density_threshold` | **Semantic gate** | Whether transcript proceeds to reactor |
| `score_threshold` / `pacing_interval` | **Reaction gates** | Whether/how often Heckler speaks back |
| `transcribe_*` fields | **Transcribe mode only** | Same capture fields, different code path |

Technician’s `pacing_interval = 6.0` only affects **output spacing**, not **input segment length**.

---

## Secondary: mic gating during TTS

`AudioCapture._emit_audio_segment` drops segments while `is_playing` is set (Kokoro playback). If the user talks over technician’s reply, that audio is discarded — separate from the 15 s / 800 ms issue but can feel like “it cut me off.”

---

## References

- `heckler/config.py` — defaults and `transcribe_*` fields
- `heckler/audio_capture.py` — VAD segmentation and 15 s force-close
- `heckler/controller.py` — `_start_persona_mode` vs `_start_transcribe_mode`
- `heckler/persona.py` — `_TOML_TO_CONFIG`, `apply_persona_overrides`
- `.dev/transcription-engine.md` — transcribe-mode VAD rationale (§ VAD tuning)
- `.dev/persona-system.md` — persona bundle shape (pre-`[capture]`)
